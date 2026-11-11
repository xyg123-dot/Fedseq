#define FEDKNN_NO_MAIN
#ifdef SYSTEM_RPC
#include "rpc_algorithm.cpp"
#else
#include "reference_algorithm.cpp"
#include <openssl/evp.h>
#endif
#include <openssl/crypto.h>
#include <fstream>
#include <sstream>

static string digest(const vector<Item>& items){
    std::ostringstream data;for(const auto& x:items)data<<x.distance<<':'<<x.provider<<':'<<x.id<<';';
    string bytes=data.str();unsigned char result[32];unsigned int size;
    if(EVP_Digest(bytes.data(),bytes.size(),result,&size,EVP_sha256(),nullptr)!=1)throw std::runtime_error("SHA256 failed");
    std::ostringstream out;for(unsigned int i=0;i<size;++i)out<<std::hex<<std::setfill('0')<<std::setw(2)<<unsigned(result[i]);return out.str();
}
#ifdef SYSTEM_RPC
static void crypto_test(){
    std::array<unsigned char,16> key{};std::array<unsigned char,12> nonce{};rpc::Bytes aad={1,2,3},plain={0,255,7,1};
    auto sealed=rpc::crypt(plain,aad,key,nonce,true);require(rpc::crypt(sealed,aad,key,nonce,false)==plain,"GCM roundtrip");
    sealed[0]^=1;bool rejected=false;try{rpc::crypt(sealed,aad,key,nonce,false);}catch(...){rejected=true;}require(rejected,"GCM altered ciphertext rejected");
    sealed[0]^=1;aad[0]^=1;rejected=false;try{rpc::crypt(sealed,aad,key,nonce,false);}catch(...){rejected=true;}require(rejected,"GCM altered AAD rejected");
    // NIST SP800-38D AES128-GCM empty-message known-answer vector.
    rpc::Bytes expected={0x58,0xe2,0xfc,0xce,0xfa,0x7e,0x30,0x61,0x36,0x7f,0x1d,0x57,0xa4,0xe7,0x45,0x5a};
    require(rpc::crypt({}, {},key,nonce,true)==expected,"GCM known-answer vector");
    std::cout<<"PASS GCM known-answer, roundtrip, ciphertext and AAD rejection\n";
}
#endif
int main(int argc,char** argv){try{
    vector<char*> filtered;filtered.push_back(argv[0]);
    for(int i=1;i<argc;++i){string a=argv[i];
#ifdef SYSTEM_RPC
        if(a=="--crypto-test"){crypto_test();return 0;}
        if(a=="--transport-rtt-ms"||a=="--transport-mbps"||a=="--encryption"){
            if(i+1==argc)throw std::runtime_error("missing transport value");
            string v=argv[++i];
            if(a=="--transport-rtt-ms")rpc::rtt_ms=std::stod(v);
            else if(a=="--transport-mbps")rpc::mbps=std::stod(v);
            else {if(v!="aes128gcm"&&v!="none")throw std::runtime_error("invalid encryption");rpc::encrypted=v!="none";}
            continue;
        }
#endif
        filtered.push_back(argv[i]);
    }
    Options o=parse(filtered.size(),filtered.data());configure(o);
    if(o.backend!="scan")throw std::runtime_error("system experiment deliberately excludes indexing");
#ifdef SYSTEM_RPC
    if(!std::isfinite(rpc::rtt_ms)||!std::isfinite(rpc::mbps)||rpc::rtt_ms<0||rpc::mbps<0)throw std::runtime_error("invalid transport profile");
#endif
    auto data=o.synthetic?synthetic(o.synthetic,o.length,o.seed,o.kind):load(o.data);
    auto queries=load(o.queries);queries.resize(std::min<size_t>(o.num_queries,queries.size()));
    if(o.k>static_cast<int>(data.size()))throw std::runtime_error("k exceeds database");
    auto build=Clock::now();auto ps=federation(data,o);double build_ms=elapsed(build);
    std::ofstream csv(o.out),nodes(o.out+".nodes.csv");if(!csv||!nodes)throw std::runtime_error("output open failed");
    csv<<std::setprecision(12);nodes<<std::setprecision(12);
    csv<<"query,repeat,algorithm,m,k,epsilon,experiment_seed,wall_ms,total_cpu_ms,broker_cpu_ms,provider_cpu_ms,crypto_cpu_ms,application_wire_bytes,frames,shape_wait_sum_ms,dp_calls,lb_evals,first_quota,second_quota,zero_first,revived,recall,strict_exact,distance_topk_exact,result_sha256,build_wall_ms,privacy,noise_rng,beta1,beta2\n";
    nodes<<"query,repeat,algorithm,provider,cpu_ms,crypto_cpu_ms,application_wire_bytes,frames\n";
    vector<string> algorithms;string a;std::stringstream names(o.algorithms);while(std::getline(names,a,','))algorithms.push_back(a);
    std::mt19937_64 order_rng(o.seed+2);int errors=0;
    for(int qi=0;qi<static_cast<int>(queries.size());++qi){
        // Oracle is exhaustive and outside measured intervals.
#ifdef SYSTEM_RPC
        double saved_rtt=rpc::rtt_ms,saved_bw=rpc::mbps;rpc::rtt_ms=rpc::mbps=0;
#endif
        Broker truth(ps,o.k,queries[qi],o.epsilon,o.lambda,0,o.seed);auto oracle=truth.oracle();
#ifdef SYSTEM_RPC
        // Child globals are fixed at fork; server-side shaping remains outside timing.
        rpc::rtt_ms=saved_rtt;rpc::mbps=saved_bw;for(auto& p:ps)p.finish_stats();
#endif
        if(qi==0)for(const auto& alg:algorithms){
#ifdef SYSTEM_RPC
            for(auto& p:ps)p.configure_wire(o.k,alg=="baseline"||alg=="dann_star"||alg=="fedseq_star");
#endif
            Broker warm(ps,o.k,queries[qi],o.epsilon,o.lambda,0,o.seed,o.privacy=="calibrated",o.noise_rng=="private");warm.run(alg);
#ifdef SYSTEM_RPC
            for(auto& p:ps)p.finish_stats();
#endif
        }
        for(int rep=0;rep<o.repeats;++rep){auto shuffled=algorithms;std::shuffle(shuffled.begin(),shuffled.end(),order_rng);
            uint64_t seed=o.seed+104729ULL*qi+1000003ULL*rep;
            for(const auto& alg:shuffled){
#ifdef SYSTEM_RPC
                bool pad=alg=="baseline"||alg=="dann_star"||alg=="fedseq_star";
                for(auto& p:ps)p.configure_wire(o.k,pad);
#endif
                Broker broker(ps,o.k,queries[qi],o.epsilon,o.lambda,0,seed,o.privacy=="calibrated",o.noise_rng=="private");
                double before=process_cpu_ms();auto start=Clock::now();auto run=broker.run(alg);double wall=elapsed(start),broker_cpu=process_cpu_ms()-before;
                double provider_cpu=0,crypto_cpu=0,wait=0;uint64_t wire=0,frames=0;
#ifdef SYSTEM_RPC
                for(auto& p:ps){auto s=p.finish_stats();provider_cpu+=s.cpu;crypto_cpu+=s.crypto;wire+=s.tx;frames+=s.frames;wait+=s.shape_wait;
                    if(s.tx!=s.rx)throw std::runtime_error("sender/receiver application bytes disagree");
                    nodes<<qi<<','<<rep<<','<<alg<<','<<p.id()<<','<<s.cpu<<','<<s.crypto<<','<<s.tx<<','<<s.frames<<'\n';}
#else
                provider_cpu=run.metrics.provider_cpu_ms;broker_cpu=run.metrics.broker_cpu_ms;
                for(int pi=0;pi<o.m;++pi)nodes<<qi<<','<<rep<<','<<alg<<','<<pi<<','<<run.metrics.provider_cpu_by_node[pi]<<",0,0,0\n";
#endif
                bool strict=run.result==oracle;vector<int> got,wanted;for(auto& x:run.result)got.push_back(x.distance);for(auto& x:oracle)wanted.push_back(x.distance);
                bool distances=got==wanted;if((alg=="baseline"||alg=="dann"||alg=="fedseq")&&!strict)++errors;
                auto& x=run.metrics;
                csv<<qi<<','<<rep<<','<<alg<<','<<o.m<<','<<o.k<<','<<o.epsilon<<','<<seed<<','<<wall<<','<<broker_cpu+provider_cpu<<','<<broker_cpu<<','<<provider_cpu<<','<<crypto_cpu<<','<<wire<<','<<frames<<','<<wait<<','<<x.dp_calls<<','<<x.lb_evals<<','<<x.first_quota<<','<<x.second_quota<<','<<x.zero_first<<','<<x.revived<<','<<recall(run.result,oracle)<<','<<strict<<','<<distances<<','<<digest(run.result)<<','<<build_ms<<','<<o.privacy<<','<<o.noise_rng<<','<<(o.privacy=="calibrated"?o.epsilon/4:o.epsilon/2)<<','<<(o.privacy=="calibrated"?o.epsilon/(2.0*(o.k+o.m)):o.epsilon/2)<<'\n';
                csv.flush();
            }
        }
    }
    std::cout<<"DONE runs="<<queries.size()*o.repeats*algorithms.size()<<" nonnoisy_errors="<<errors<<" OpenSSL="<<OpenSSL_version(OPENSSL_VERSION)<<"\n";return errors?2:0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
