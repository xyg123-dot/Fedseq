#pragma once
// Local TCP process experiment. This is not an SGX enclave or attested channel.
#include <openssl/evp.h>
#include <openssl/rand.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <unistd.h>
#include <thread>
#include <cstring>
#include <cerrno>
#include <csignal>

namespace rpc {
using Bytes=std::vector<unsigned char>;
inline bool encrypted=true;
inline double rtt_ms=0,mbps=0;
struct Stats { double cpu=0,crypto=0,shape_wait=0; uint64_t tx=0,rx=0,frames=0; };
inline double thread_cpu_ms(){timespec t;
    if(clock_gettime(CLOCK_THREAD_CPUTIME_ID,&t))throw std::runtime_error("thread CPU clock failed");
    return t.tv_sec*1000.0+t.tv_nsec/1000000.0;}
struct Buffer {
    Bytes b; size_t pos=0;
    void u32(uint32_t x){for(int i=3;i>=0;--i)b.push_back(x>>(8*i));}
    uint32_t u32(){need(4);uint32_t x=0;for(int i=0;i<4;++i)x=(x<<8)|b[pos++];return x;}
    void u64(uint64_t x){u32(x>>32);u32(x);}
    uint64_t u64(){uint64_t x=u32();return (x<<32)|u32();}
    void number(double x){uint64_t n;std::memcpy(&n,&x,8);u64(n);}
    double number(){uint64_t n=u64();double x;std::memcpy(&x,&n,8);return x;}
    void need(size_t n){if(n>b.size()-pos)throw std::runtime_error("truncated RPC");}
    void text(const string& s){u32(s.size());b.insert(b.end(),s.begin(),s.end());}
    string text(){size_t n=u32();need(n);string s(b.begin()+pos,b.begin()+pos+n);pos+=n;return s;}
    void item(const Item& x){u32(x.distance);u32(x.provider);u32(x.id);}
    Item item(){int d=static_cast<int32_t>(u32()),p=static_cast<int32_t>(u32()),id=static_cast<int32_t>(u32());return {d,p,id};}
    void work(const Work& w){u64(w.dp);u64(w.lb);u64(w.cache_hits);u64(w.index_probes);u64(w.order_lb);number(w.lb_cpu_ms);number(w.order_lb_cpu_ms);}
    Work work(){Work w;w.dp=u64();w.lb=u64();w.cache_hits=u64();w.index_probes=u64();w.order_lb=u64();w.lb_cpu_ms=number();w.order_lb_cpu_ms=number();return w;}
    void stats(const Stats& s){number(s.cpu);number(s.crypto);number(s.shape_wait);u64(s.tx);u64(s.rx);u64(s.frames);}
    Stats stats(){Stats s;s.cpu=number();s.crypto=number();s.shape_wait=number();s.tx=u64();s.rx=u64();s.frames=u64();return s;}
    void end(){if(pos!=b.size())throw std::runtime_error("trailing RPC data");}
};
inline void checked(bool ok,const char* msg){if(!ok)throw std::runtime_error(msg);}
inline void io(int fd,unsigned char* p,size_t n,bool writing){
    while(n){ssize_t done=writing ? ::send(fd,p,n,MSG_NOSIGNAL) : ::recv(fd,p,n,0);
        if(done<0&&errno==EINTR)continue;
        if(done<=0)throw std::runtime_error("TCP peer disconnected");
        n-=done;p+=done;
    }
}
inline Bytes crypt(const Bytes& in,const Bytes& aad,const std::array<unsigned char,16>& key,
                   const std::array<unsigned char,12>& nonce,bool seal){
    checked(seal||in.size()>=16,"missing GCM tag");
    auto ctx=std::unique_ptr<EVP_CIPHER_CTX,decltype(&EVP_CIPHER_CTX_free)>(EVP_CIPHER_CTX_new(),EVP_CIPHER_CTX_free);
    checked(bool(ctx),"EVP allocation failed");
    size_t n=seal?in.size():in.size()-16;Bytes out(n+16);int used=0,last=0,tmp=0;
    checked(EVP_CipherInit_ex(ctx.get(),EVP_aes_128_gcm(),nullptr,nullptr,nullptr,seal)==1,"GCM init failed");
    checked(EVP_CIPHER_CTX_ctrl(ctx.get(),EVP_CTRL_GCM_SET_IVLEN,12,nullptr)==1,"GCM IV failed");
    checked(EVP_CipherInit_ex(ctx.get(),nullptr,nullptr,key.data(),nonce.data(),seal)==1,"GCM key failed");
    checked(EVP_CipherUpdate(ctx.get(),nullptr,&tmp,aad.data(),aad.size())==1,"GCM AAD failed");
    checked(EVP_CipherUpdate(ctx.get(),out.data(),&used,in.data(),n)==1,"GCM update failed");
    if(!seal)checked(EVP_CIPHER_CTX_ctrl(ctx.get(),EVP_CTRL_GCM_SET_TAG,16,const_cast<unsigned char*>(in.data()+n))==1,"GCM tag failed");
    checked(EVP_CipherFinal_ex(ctx.get(),out.data()+used,&last)==1,"GCM authentication failed");
    out.resize(used+last+(seal?16:0));
    if(seal)checked(EVP_CIPHER_CTX_ctrl(ctx.get(),EVP_CTRL_GCM_GET_TAG,16,out.data()+used+last)==1,"GCM get tag failed");
    return out;
}
struct Channel {
    int fd=-1;std::array<unsigned char,16> txkey{},rxkey{};
    uint64_t txseq=0,rxseq=0;Stats stats;
    Channel()=default;
    Channel(int f,std::array<unsigned char,16> a,std::array<unsigned char,16> b):fd(f),txkey(a),rxkey(b){}
    static std::array<unsigned char,12> nonce(uint64_t seq){
        std::array<unsigned char,12> n{};for(int i=0;i<8;++i)n[11-i]=seq>>(8*i);return n;
    }
    void send(const Bytes& plain,bool shaped){
        if(txseq==UINT64_MAX)throw std::runtime_error("GCM counter exhausted");
        Buffer h;h.u32(plain.size()+(encrypted?16:0));h.u64(txseq);
        double c=thread_cpu_ms();auto payload=encrypted?crypt(plain,h.b,txkey,nonce(txseq),true):plain;
        if(encrypted)stats.crypto+=thread_cpu_ms()-c;
        ++txseq;
        size_t bytes=h.b.size()+payload.size();
        if(shaped){double wait=rtt_ms/2+(mbps>0?bytes*8.0/(mbps*1000):0);
            auto t=Clock::now();std::this_thread::sleep_for(std::chrono::duration<double,std::milli>(wait));stats.shape_wait+=elapsed(t);}
        io(fd,h.b.data(),h.b.size(),true);io(fd,payload.data(),payload.size(),true);stats.tx+=bytes;++stats.frames;
    }
    Bytes receive(){
        Buffer h;h.b.resize(12);io(fd,h.b.data(),12,false);size_t n=h.u32();auto seq=h.u64();
        if(n>64*1024*1024||seq!=rxseq)throw std::runtime_error("invalid frame size/replayed sequence");
        Bytes payload(n);io(fd,payload.data(),n,false);double c=thread_cpu_ms();
        Bytes plain=encrypted?crypt(payload,h.b,rxkey,nonce(rxseq),false):payload;
        if(encrypted)stats.crypto+=thread_cpu_ms()-c;
        ++rxseq;stats.rx+=12+n;return plain;
    }
};
inline void socket_options(int fd){int on=1;setsockopt(fd,IPPROTO_TCP,TCP_NODELAY,&on,sizeof(on));
    timeval timeout{30,0};setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof(timeout));}
}

class Provider {
    int pid=0,n=0;pid_t child=-1;rpc::Channel channel;
    string pending_query;bool pending=false,use_order=false,padded=false,frontier_needed=false;
    int global_k=0,slot_width=0;Item frontier{};
    static void server(int listener,LocalProvider& local,int width,
                       std::array<unsigned char,16> requestkey,std::array<unsigned char,16> responsekey){
        int fd=accept(listener,nullptr,nullptr);close(listener);if(fd<0)_exit(2);
        rpc::socket_options(fd);rpc::Channel ch(fd,responsekey,requestkey);
        rpc::Stats total;int k=0;bool pad=false;
        try {for(;;){double begin=process_cpu_ms();auto previous=ch.stats;rpc::Buffer req;req.b=ch.receive();uint32_t op=req.u32();
            if(op==9){req.end();total.crypto=previous.crypto;total.tx=previous.tx;total.rx=previous.rx;total.frames=previous.frames;total.shape_wait=previous.shape_wait;
                rpc::Buffer out;out.stats(total);ch.send(out.b,false);total={};ch.stats={};continue;}
            if(op==8){req.end();break;}
            if(req.u32()){string query=req.text();bool order=req.u32();k=req.u32();pad=req.u32();local.reset(query,calsig(query),order);}
            int target=static_cast<int>(req.u32());bool extra=req.u32();req.end();
            vector<Item> items;
            if(op==1)items=local.local_klb(target,extra);
            else if(op==2)items=local.local_knn(target);
            else if(op==3)items=local.oracle();
            else throw std::runtime_error("invalid RPC operation");
            rpc::Buffer out;out.work(local.work);
            bool result=op!=1;size_t slots=result&&pad&&op!=3?static_cast<size_t>(k):items.size();
            out.u32(slots);
            for(size_t j=0;j<slots;++j){bool real=j<items.size();out.u32(real);out.item(real?items[j]:Item{INT_MAX,local.id(),-1});
                if(result){string seq=real?local.sequence(items[j].id):string();
                    out.u32(seq.size());out.b.insert(out.b.end(),seq.begin(),seq.end());out.b.insert(out.b.end(),width-seq.size(),0);}}
            // Piggyback the actual unseen frontier, avoiding an artificial extra round.
            bool has_frontier=op==2&&extra;out.u32(has_frontier);
            if(has_frontier)out.item(local.unseen_frontier(items));
            ch.send(out.b,true);total.cpu+=process_cpu_ms()-begin;
        }}catch(const std::exception& e){std::cerr<<"provider "<<local.id()<<": "<<e.what()<<"\n";close(fd);_exit(3);}
        close(fd);_exit(0);
    }
    vector<Item> request(int op,int target,bool extra){
        rpc::Buffer req;req.u32(op);req.u32(pending);
        if(pending){req.text(pending_query);req.u32(use_order);req.u32(global_k);req.u32(padded);pending=false;}
        req.u32(target);req.u32(extra);channel.send(req.b,true);
        rpc::Buffer response;response.b=channel.receive();work=response.work();size_t slots=response.u32();vector<Item> items;
        for(size_t j=0;j<slots;++j){bool real=response.u32();Item item=response.item();
            if(op!=1){size_t size=response.u32();if(size>static_cast<size_t>(slot_width))throw std::runtime_error("invalid slot length");
                response.need(slot_width); // Sequence bytes genuinely encrypted and transmitted.
                response.pos+=slot_width;}
            if(real)items.push_back(item);
        }
        bool has=response.u32();if(has)frontier=response.item();response.end();return items;
    }
public:
    Work work;
    Provider(int p,vector<pair<int,string>> rows,string backend,double alpha):pid(p),n(rows.size()){
        for(auto& row:rows)slot_width=std::max(slot_width,static_cast<int>(row.second.size()));
        LocalProvider local(p,std::move(rows),std::move(backend),alpha);
        int listener=socket(AF_INET,SOCK_STREAM,0);rpc::checked(listener>=0,"TCP socket failed");
        sockaddr_in addr{};addr.sin_family=AF_INET;addr.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
        rpc::checked(bind(listener,reinterpret_cast<sockaddr*>(&addr),sizeof(addr))==0,"TCP bind failed");
        socklen_t len=sizeof(addr);getsockname(listener,reinterpret_cast<sockaddr*>(&addr),&len);listen(listener,1);
        std::array<unsigned char,16> a{},b{};rpc::checked(RAND_bytes(a.data(),16)==1&&RAND_bytes(b.data(),16)==1,"key generation failed");
        child=fork();rpc::checked(child>=0,"fork failed");
        if(child==0){
            // Do not retain inherited channels belonging to other providers.
            for(int fd=3;fd<1024;++fd)if(fd!=listener)close(fd);
            server(listener,local,slot_width,a,b);
        }
        int fd=socket(AF_INET,SOCK_STREAM,0);rpc::socket_options(fd);
        rpc::checked(connect(fd,reinterpret_cast<sockaddr*>(&addr),sizeof(addr))==0,"TCP connect failed");
        close(listener);channel=rpc::Channel(fd,a,b);
    }
    Provider(const Provider&)=delete;Provider& operator=(const Provider&)=delete;
    Provider(Provider&& other) noexcept:pid(other.pid),n(other.n),child(other.child),channel(std::move(other.channel)),slot_width(other.slot_width){other.child=-1;other.channel.fd=-1;}
    ~Provider(){if(channel.fd>=0){try{rpc::Buffer req;req.u32(8);channel.send(req.b,false);}catch(...){if(child>0)kill(child,SIGTERM);}close(channel.fd);}if(child>0)waitpid(child,nullptr,0);}
    int id() const{return pid;}int size() const{return n;}
    void configure_wire(int k,bool pad){global_k=k;padded=pad;}
    void reset(const string& s,const vector<int>&,bool order=false){pending_query=s;pending=true;use_order=order;frontier_needed=false;work={};}
    void want_frontier(bool wanted){frontier_needed=wanted;}
    vector<Item> local_klb(int k,bool enabled){return request(1,k,enabled);}
    vector<Item> local_knn(int k){return request(2,k,frontier_needed);}
    vector<Item> oracle(){return request(3,n,false);}
    Item unseen_frontier(const vector<Item>&){return frontier;}
    rpc::Stats finish_stats(){rpc::Stats client=channel.stats;rpc::Buffer req;req.u32(9);channel.send(req.b,false);
        rpc::Buffer response;response.b=channel.receive();auto server=response.stats();response.end();
        // Count each TCP application byte once, from its sender.
        server.crypto+=client.crypto;server.tx+=client.tx;server.rx+=client.rx;
        server.frames+=client.frames;server.shape_wait+=client.shape_wait;channel.stats={};return server;}
};
