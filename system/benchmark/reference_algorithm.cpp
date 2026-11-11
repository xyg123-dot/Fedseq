// Algorithm-level FedKNN reproduction; not an SGX or oblivious implementation.
// Local MinSearch port is derived from https://github.com/kedayuge/Search.
#include "minsearch.h"
#include "order_bound.h"
#include <chrono>
#include <ctime>
#include <random>
#include <set>
#include <stdexcept>
#include <iomanip>
#include <memory>
#include <cmath>
#include <array>
#include <limits>
#include <openssl/rand.h>

int q=2, countbit=1;
string qtype="-k";
using Clock=std::chrono::steady_clock;
static double elapsed(Clock::time_point t) {
    return std::chrono::duration<double,std::milli>(Clock::now()-t).count();
}
// Process CPU includes user+system CPU, excluding waits. Serial role simulation.
static double process_cpu_ms() {
#if defined(CLOCK_PROCESS_CPUTIME_ID)
    struct timespec t;
    if(clock_gettime(CLOCK_PROCESS_CPUTIME_ID,&t)!=0)throw std::runtime_error("CPU clock failed");
    return t.tv_sec*1000.0+t.tv_nsec/1000000.0;
#else
    return 1000.0*std::clock()/CLOCKS_PER_SEC;
#endif
}
struct Item {
    int distance, provider, id;
    bool operator<(const Item& b) const {
        return std::tie(distance,provider,id)<std::tie(b.distance,b.provider,b.id);
    }
    bool operator==(const Item& b) const {
        return std::tie(distance,provider,id)==std::tie(b.distance,b.provider,b.id);
    }
};
// Ordinary ordered set. Its name deliberately makes no obliviousness claim.
class TopK {
    int k;
    std::set<Item> data;
public:
    explicit TopK(int n):k(n){}
    void insert(const Item& x) {
        data.insert(x);
        if (static_cast<int>(data.size())>k) data.erase(std::prev(data.end()));
    }
    int rank(const Item& x) const {
        auto it=data.find(x);
        return it==data.end()?0:static_cast<int>(std::distance(data.begin(),it))+1;
    }
    int preceding(const Item& x) const {
        return static_cast<int>(std::distance(data.begin(),data.lower_bound(x)));
    }
    vector<Item> values() const { return {data.begin(),data.end()}; }
};
static vector<unsigned short> bigrams(const string& s) {
    vector<unsigned short> out;
    for(size_t i=1;i<s.size();++i)
        out.push_back((static_cast<unsigned char>(s[i-1])<<8)|static_cast<unsigned char>(s[i]));
    std::sort(out.begin(),out.end());return out;
}
static int bigram_bound(const vector<unsigned short>& a,const vector<unsigned short>& b) {
    size_t i=0,j=0,common=0;
    while(i<a.size()&&j<b.size()) {
        if(a[i]==b[j]){++common;++i;++j;}
        else if(a[i]<b[j])++i;else ++j;
    }
    return static_cast<int>((a.size()+b.size()-2*common+3)/4);
}
struct Record { int id; string seq; vector<int> signature;vector<unsigned short> grams2; };
struct Work {
    long long dp=0, lb=0, cache_hits=0, index_probes=0;
    long long order_lb=0;
    double lb_cpu_ms=0,order_lb_cpu_ms=0;
};
// Distance is Levenshtein on bytes, consistent with the supplied edit_dp.
// Signature gram width is countbit, independently of MinSearch anchor width q.
static int lower_bound_distance(const vector<int>& a,int alen,const vector<int>& b,int blen) {
    if (a.size()!=b.size()) throw std::logic_error("signature dimensions disagree");
    long long diff=0;
    for(size_t i=0;i<a.size();++i) diff+=std::abs(a[i]-b[i]);
    return std::max(std::abs(alen-blen),static_cast<int>((diff+2*countbit-1)/(2*countbit)));
}
using Index=unordered_map<int,unordered_map<string,vector<pair<int,int>>>>;
class Provider {
    int pid;
    vector<Record> db;
    Index index;
    string backend;
    double alpha;
    string query;
    vector<int> query_sig;
    vector<unsigned short> query_grams2;
    bool use_grams2=false;
    vector<Item> lbs;
    vector<int> order;
    vector<int> cache; // Exact cached values only; -1 means unknown.
    bool indexed_ready=false;
    int indexed_target=0;
    vector<Item> indexed_result;
    std::unique_ptr<OrderBound> order_pattern;
public:
    Work work;
    Provider(int p,vector<pair<int,string>> rows,string engine,double a)
        :pid(p),backend(std::move(engine)),alpha(a) {
        // Upstream sorts by length and lexicographic order before indexing.
        std::sort(rows.begin(),rows.end(),[](const auto& x,const auto& y){
            return std::make_tuple(x.second.size(),x.second,x.first)<
                   std::make_tuple(y.second.size(),y.second,y.first);
        });
        for(auto& row:rows) db.push_back({row.first,row.second,calsig(row.second),bigrams(row.second)});
        if(backend!="scan") {
            for(int i=0;i<static_cast<int>(db.size());++i) {
                auto parts=partition(db[i].seq);
                for(auto& level:parts) for(auto& piece:level.second)
                    index[level.first][piece.first].push_back({i,piece.second});
            }
            for(auto& level:index) for(auto& piece:level.second)
                std::sort(piece.second.begin(),piece.second.end(),[](auto x,auto y){return x.second<y.second;});
        }
    }
    int id() const {return pid;}
    int size() const {return static_cast<int>(db.size());}
    void reset(const string& s,const vector<int>& sig,bool use_order=false,bool gram2=false) {
        query=s; query_sig=sig; work={}; lbs.clear();order.clear();
        cache.assign(db.size(),-1); indexed_ready=false; indexed_target=0; indexed_result.clear();
        order_pattern=use_order?std::make_unique<OrderBound>(s):nullptr;
        use_grams2=gram2;query_grams2=gram2?bigrams(s):vector<unsigned short>{};
    }
    void prepare_bounds() {
        if(lbs.size()==db.size() && !order.empty()) return;
        double cpu=process_cpu_ms();
        lbs.clear();order.resize(db.size());
        for(int i=0;i<size();++i) {
            lbs.push_back({lower_bound_distance(db[i].signature,db[i].seq.size(),query_sig,query.size()),pid,db[i].id});
            if(use_grams2)lbs.back().distance=std::max(lbs.back().distance,bigram_bound(db[i].grams2,query_grams2));
            order[i]=i;++work.lb;
        }
        if(order_pattern) {
            double oc=process_cpu_ms();
            for(int i=0;i<size();++i) {
                lbs[i].distance=std::max(lbs[i].distance,order_pattern->lower(db[i].seq));
                ++work.order_lb;
            }
            work.order_lb_cpu_ms+=process_cpu_ms()-oc;
        }
        std::sort(order.begin(),order.end(),[&](int i,int j){return lbs[i]<lbs[j];});
        work.lb_cpu_ms+=process_cpu_ms()-cpu;
    }
    vector<Item> local_klb(int k,bool enabled) {
        prepare_bounds(); vector<Item> result;
        for(int i=0;i<std::min(k,size());++i) {
            Item x=lbs[order[i]];
            if(!enabled) x.distance=std::numeric_limits<int>::max();
            result.push_back(x);
        }
        return result;
    }
    int exact(int i) {
        if(cache[i]>=0) {++work.cache_hits;return cache[i];}
        ++work.dp; return cache[i]=edit_dp(db[i].seq,query);
    }
    vector<Item> scan_topk(int k,const vector<Item>& seeds={}) {
        prepare_bounds();TopK result(k);
        for(const auto& x:seeds) result.insert(x);
        for(int i:order) {
            auto values=result.values();
            if(static_cast<int>(values.size())==k && !(lbs[i]<values.back())) break;
            result.insert({exact(i),pid,db[i].id});
        }
        return result.values();
    }
    // Faithful MinSearch structure: descend partition levels, probe inverted buckets,
    // length/count filtering, bounded edit verification, alpha-based level stopping.
    // Safety/tie changes are documented in REPRODUCTION_NOTES.md; MinSearch remains probabilistic.
    vector<Item> minsearch_topk(int k) {
        if(indexed_ready && k<=indexed_target) {
            auto r=indexed_result;if(static_cast<int>(r.size())>k) r.resize(k);return r;
        }
        TopK result(k); vector<bool> verified(db.size(),false);
        int min_level=INT_MIN;
        // Upstream starts at query.length(); length gaps can exceed it. Use an
        // unbounded initial cutoff until k verified results exist.
        auto parts=partition(query);
        for(auto& level:parts) {
            auto il=index.find(level.first);if(il==index.end()) continue;
            auto values=result.values();
            bool full=static_cast<int>(values.size())==k;
            if(full && level.first<min_level) break;
            for(auto& piece:level.second) {
                auto bucket=il->second.find(piece.first);if(bucket==il->second.end()) continue;
                values=result.values();full=static_cast<int>(values.size())==k;
                int cutoff=full?values.back().distance:INT_MAX/4;
                auto it=std::lower_bound(bucket->second.begin(),bucket->second.end(),piece.second-cutoff,
                    [](auto x,int pos){return x.second<pos;});
                for(;it!=bucket->second.end();++it) {
                    if(it->second>piece.second+cutoff) break;
                    ++work.index_probes;int j=it->first;
                    if(verified[j]) continue;
                    values=result.values();full=static_cast<int>(values.size())==k;
                    cutoff=full?values.back().distance:INT_MAX/4;
                    if(full && (!lengthfilter(db[j].seq,query,it->second,piece.second,cutoff) ||
                                !countfilter(db[j].signature,query_sig,cutoff))) continue;
                    verified[j]=true;
                    int d;
                    if(cache[j]>=0) {d=cache[j];++work.cache_hits;}
                    else {
                        ++work.dp;
                        d=full?edit_dp(db[j].seq,query,cutoff):edit_dp(db[j].seq,query);
                        if(d>=0) cache[j]=d;
                    }
                    if(d>=0) result.insert({d,pid,db[j].id});
                }
            }
            values=result.values();
            if(static_cast<int>(values.size())==k)
                min_level=std::max(1,static_cast<int>(query.size()/(2*alpha*std::max(values.back().distance,1)+2)));
        }
        indexed_result=result.values();indexed_target=k;indexed_ready=true;
        return indexed_result;
    }
    vector<Item> local_knn(int n) {
        n=std::min(n,size());if(n<=0)return {};
        if(backend=="scan") return scan_topk(n);
        auto r=minsearch_topk(n);
        if(backend=="minsearch-certified") return scan_topk(n,r);
        return r;
    }
    vector<Item> oracle() const {
        vector<Item> out;for(auto& x:db)out.push_back({edit_dp(x.seq,query),pid,x.id});return out;
    }
    Item unseen_frontier(const vector<Item>& sent) {
        prepare_bounds();std::set<int> ids;for(const auto& x:sent)ids.insert(x.id);
        for(int i:order)if(!ids.count(db[i].id))return lbs[i];
        return {INT_MAX,pid,INT_MAX};
    }
};
struct Metrics {
    double wall_ms=0,total_cpu_ms=0,provider_cpu_ms=0,broker_cpu_ms=0;
    double provider_work_ms=0,broker_work_ms=0,parallel_compute_est_ms=0,modeled_e2e_ms=0;
    vector<double> provider_cpu_by_node;
    long long dp_calls=0,lb_evals=0,cache_hits=0,index_probes=0,first_quota=0,second_quota=0;
    long long unique_quota=0,lb_wire_records=0,result_wire_records=0;
    int rounds=0;
    long long order_lb_evals=0,frontier_wire_records=0;
    double lb_cpu_ms=0,order_lb_cpu_ms=0;
    int zero_first=0,revived=0,dann_fallback=0,order_lb_enabled=0;
};
struct Allocation {
    int initial=0,first=0,actual_first=0,rank=0,target=0,second=0,actual_second=0;
    double first_laplace=0,second_laplace=0,offset=0,second_offset=0;
};
struct Run { vector<Item> result; Metrics metrics; vector<Allocation> allocations; };
struct ResultSlot { bool dummy; Item value; };
class Broker {
    vector<Provider>& providers;
    int k;
    string query;
    vector<int> signature;
    double epsilon,lambda,rtt;
    std::mt19937_64 rng;
    bool calibrated,private_rng;
    double rate1,rate2,active_rate;
    double uniform_open() {
        uint64_t value;
        if(private_rng) {
            if(RAND_bytes(reinterpret_cast<unsigned char*>(&value),sizeof(value))!=1)
                throw std::runtime_error("private random generation failed");
        } else value=rng();
        return (static_cast<double>(value>>12)+0.5)/4503599627370496.0;
    }
    double laplace() {
        double x=-std::log(uniform_open())/active_rate;
        double y=-std::log(uniform_open())/active_rate;
        return x-y;
    }
    int noisy(int count,double& sample) {
        sample=laplace();
        double value=count-std::log(2*lambda)/active_rate+sample;
        // Algorithm 2 Line 13 clips to [1,k]. Paper does not specify rounding.
        if(value>=k)return k;
        if(value<=1)return 1;
        return static_cast<int>(std::ceil(value));
    }
    double geometric_offset() const {
        double e=active_rate,a=std::exp(-e);
        return std::max(0.0,std::ceil(-std::log(lambda*(1+a))/e)-1);
    }
    int noisy_zero(int count,double& sample) {
        sample=laplace();double value=count-std::log(2*lambda)/active_rate+sample;
        if(value>=k)return k;
        if(value<=0)return 0;
        return static_cast<int>(std::ceil(value));
    }
    int geometric_noisy(int count,double& sample) {
        double x=std::floor(-std::log(uniform_open())/active_rate);
        double y=std::floor(-std::log(uniform_open())/active_rate);
        sample=x-y;
        double value=count+geometric_offset()+sample;
        if(value>=k)return k;
        if(value<=0)return 0;
        return static_cast<int>(value);
    }
public:
    Broker(vector<Provider>& ps,int n,string s,double eps,double lam,double net,uint64_t seed,
           bool calibrate=true,bool private_random=false)
        :providers(ps),k(n),query(std::move(s)),epsilon(eps),lambda(lam),rtt(net),rng(seed),
         calibrated(calibrate),private_rng(private_random) {
        if(k<1||epsilon<=0||!std::isfinite(epsilon)||lambda<=0||lambda>=.5||!std::isfinite(lambda))
            throw std::invalid_argument("require k>0, epsilon>0, 0<lambda<0.5");
        signature=calsig(query);
        rate1=calibrated?epsilon/4:epsilon/2;
        // Common bound for both DANN* and branch-stable FedSeq*: Delta2 <= k+m.
        rate2=calibrated?epsilon/(2.0*(k+providers.size())):epsilon/2;
        active_rate=rate1;
    }
    Run run(const string& algorithm,bool with_lb=true,const vector<int>* forced_first=nullptr) {
        bool seq=algorithm=="fedseq"||algorithm=="fedseq_legacy"||algorithm=="fedseq_star"||algorithm=="fedseq_star_laplace"||algorithm=="fedseq_star_laplace_zero";
        bool order_lb=algorithm=="fedseq"||algorithm=="dann_order"||algorithm=="fedseq_star"||algorithm=="fedseq_star_laplace"||algorithm=="dann_order_star"||algorithm=="fedseq_star_laplace_zero";
        if(algorithm!="baseline"&&algorithm!="dann"&&algorithm!="dann_star"&&!seq&&algorithm!="dann_order"&&algorithm!="dann_order_star"&&algorithm!="dann_gram2")
            throw std::invalid_argument("unknown reference algorithm");
        auto start=Clock::now();double cpu_start=process_cpu_ms();
        Run out;auto& mt=out.metrics;TopK results(k);int m=providers.size();
        mt.provider_cpu_by_node.assign(m,0);out.allocations.resize(m);
        vector<int> clean(m,0),first(m,0),second(m,0);
        vector<vector<Item>> r1(m),r2(m);
        vector<Item> frontiers(m);
        vector<vector<ResultSlot>> wire1(m),wire2(m);
        bool base=algorithm=="baseline",star=algorithm=="dann_star"||algorithm=="fedseq_star"||algorithm=="fedseq_star_laplace"||algorithm=="dann_order_star"||algorithm=="fedseq_star_laplace_zero";
        bool geometric=algorithm=="fedseq_star";
        auto perturb=[&](int count,double& sample){return geometric?geometric_noisy(count,sample):algorithm=="fedseq_star_laplace_zero"?noisy_zero(count,sample):noisy(count,sample);};
        auto provider_phase=[&](auto action) {
            double mx=0;
            for(int i=0;i<m;++i) {
                auto t=Clock::now();double pc=process_cpu_ms();action(i);
                double cpu=process_cpu_ms()-pc,d=elapsed(t);
                mt.provider_cpu_ms+=cpu;mt.provider_cpu_by_node[i]+=cpu;
                mt.provider_work_ms+=d;mx=std::max(mx,d);
            }
            mt.parallel_compute_est_ms+=mx;
        };
        mt.order_lb_enabled=order_lb;
        provider_phase([&](int i){providers[i].reset(query,signature,order_lb,algorithm=="dann_gram2");});
        auto package=[&](int i,const vector<Item>& real,vector<ResultSlot>& wire) {
            // Materialize k slots for DANN*, but ordinary RAM/branches are NOT oblivious.
            size_t slots=star?static_cast<size_t>(k):real.size();wire.reserve(slots);
            for(auto& x:real)wire.push_back({false,x});
            while(wire.size()<slots)wire.push_back({true,{INT_MAX,i,-1}});
        };
        auto aggregate=[&](const vector<vector<ResultSlot>>& batches) {
            auto t=Clock::now();
            for(auto& batch:batches)for(auto& slot:batch)if(!slot.dummy)results.insert(slot.value);
            double d=elapsed(t);mt.broker_work_ms+=d;mt.parallel_compute_est_ms+=d;
        };
        if(base) {
            // Baseline: every provider computes local top-k, broker merges global top-k.
            provider_phase([&](int i){first[i]=k;r1[i]=providers[i].local_knn(k);package(i,r1[i],wire1[i]);});
            aggregate(wire1);mt.rounds=1;
        } else {
            // Algorithm 1/2 Lines 5-10: merge local top-k LB, count origins, force >=1.
            vector<vector<Item>> lower(m);
            provider_phase([&](int i){lower[i]=providers[i].local_klb(k,with_lb);});
            auto t=Clock::now();TopK lbq(k);
            for(auto& batch:lower)for(auto& x:batch)lbq.insert(x);
            for(auto& x:lbq.values())++clean[x.provider];
            // Private FedSeq always uses the frontier formula: no raw-data branch switch.
            bool cold_policy=seq&&(star||std::find(clean.begin(),clean.end(),0)!=clean.end());
            mt.dann_fallback=seq&&!cold_policy;
            for(int i=0;i<m;++i) {
                if(!cold_policy)clean[i]=std::max(clean[i],1);
                auto& a=out.allocations[i];a.initial=clean[i];
                active_rate=rate1;
                a.offset=star?(geometric?geometric_offset():-std::log(2*lambda)/active_rate):0;
                first[i]=star?perturb(clean[i],a.first_laplace):clean[i];
                if(forced_first)first[i]=forced_first->at(i);
                mt.zero_first+=first[i]==0;
            }
            double d=elapsed(t);mt.broker_work_ms+=d;mt.parallel_compute_est_ms+=d;
            // Algorithm 1 Lines 11-14 / Algorithm 2 Lines 11-16.
            provider_phase([&](int i){
                r1[i]=providers[i].local_knn(first[i]);package(i,r1[i],wire1[i]);
                if(cold_policy)frontiers[i]=providers[i].unseen_frontier(r1[i]);
            });
            if(cold_policy)mt.frontier_wire_records=m;
            aggregate(wire1);t=Clock::now();
            for(int i=0;i<m;++i) {
                int rank=r1[i].empty()?0:results.rank(r1[i].back());
                auto& a=out.allocations[i];a.rank=rank;
                // q_i=k if last real result is outside global candidate top-k (or empty).
                // Keep CLEAN kMap in Algorithm 2: do not silently use noisy/actual count.
                if(cold_policy) {
                    // Every unseen exact key >= this frontier. A preceding REAL
                    // candidate certifies one rank; the kth LB is never a cutoff.
                    int lb_rank=results.preceding(frontiers[i]);
                    int last_rank=r1[i].empty()?0:results.preceding(r1[i].back())+(rank>0);
                    int safe_rank=std::max(lb_rank,last_rank);
                    clean[i]=std::min(k,static_cast<int>(r1[i].size())+k-safe_rank);
                } else {
                    int qi=rank==0?k:rank;
                    clean[i]=clean[i]+k-qi;
                }
                a.target=clean[i];
                active_rate=rate2;
                a.second_offset=star?(geometric?geometric_offset():-std::log(2*lambda)/active_rate):0;
                second[i]=star?perturb(clean[i],a.second_laplace):clean[i];
                mt.revived+=first[i]==0&&second[i]>0&&providers[i].size()>0;
            }
            d=elapsed(t);mt.broker_work_ms+=d;mt.parallel_compute_est_ms+=d;
            // Second round retains first-round results, exactly as the paper queue r does.
            provider_phase([&](int i){r2[i]=providers[i].local_knn(second[i]);package(i,r2[i],wire2[i]);});
            aggregate(wire2);mt.rounds=3;mt.lb_wire_records=static_cast<long long>(m)*k;
        }
        for(int i=0;i<m;++i) {
            auto& a=out.allocations[i];a.first=first[i];a.second=second[i];
            a.actual_first=r1[i].size();a.actual_second=r2[i].size();
            mt.first_quota+=first[i];mt.second_quota+=second[i];
            mt.unique_quota+=std::max(first[i],second[i]);
            auto w=providers[i].work;mt.dp_calls+=w.dp;mt.lb_evals+=w.lb;
            mt.cache_hits+=w.cache_hits;mt.index_probes+=w.index_probes;
            mt.order_lb_evals+=w.order_lb;mt.lb_cpu_ms+=w.lb_cpu_ms;mt.order_lb_cpu_ms+=w.order_lb_cpu_ms;
            mt.result_wire_records+=wire1[i].size()+wire2[i].size();
        }
        out.result=results.values();mt.total_cpu_ms=process_cpu_ms()-cpu_start;
        mt.broker_cpu_ms=mt.total_cpu_ms-mt.provider_cpu_ms;mt.wall_ms=elapsed(start);
        mt.modeled_e2e_ms=mt.parallel_compute_est_ms+mt.rounds*rtt;
        return out;
    }
    vector<Item> oracle() {
        TopK r(k);for(auto& p:providers){p.reset(query,signature);for(auto& x:p.oracle())r.insert(x);}return r.values();
    }
};

struct Options {
    string data,queries,out="results.csv",backend="scan",split="zipf",kind="dna";
    string assignment;
    string privacy="calibrated",noise_rng="private";
    string algorithms="baseline,dann,fedseq_legacy,dann_order,fedseq";
    int m=8,k=128,num_queries=50,repeats=3,synthetic=0,length=80,gram=1,anchor=0;
    uint64_t seed=42;
    double skew=0.6,epsilon=1,lambda=0.05,rtt=64,alpha=2;
    bool self_test=false,no_lb=false;
};
static vector<string> load(const string& path) {
    std::ifstream f(path);if(!f)throw std::runtime_error("cannot open: "+path);
    vector<string> data;string line;
    while(std::getline(f,line)) {if(!line.empty()&&line.back()=='\r')line.pop_back();data.push_back(line);}
    if(data.empty())throw std::runtime_error("empty data file: "+path);
    return data;
}
static void configure(const Options& o) {
    dict.clear();dictsize=o.kind=="dna"?5:32;countbit=o.gram;q=o.anchor?o.anchor:(o.kind=="dna"?8:2);if(q*static_cast<int>(std::ceil(std::log2(dictsize)))>30)
        throw std::invalid_argument("anchor width exceeds legacy hash mask capacity");
    initiHash();
}
static vector<string> synthetic(int n,int length,uint64_t seed,string kind) {
    std::mt19937_64 rng(seed);string alphabet=kind=="dna"?"ACGT":"abcdefghijklmnopqrstuvwxyz ";
    vector<string> centers(8,string(length,'A'));for(auto& s:centers)for(auto& c:s)c=alphabet[rng()%alphabet.size()];
    vector<string> data;for(int i=0;i<n;++i) {
        string s=centers[i%centers.size()];
        for(int j=0;j<1+static_cast<int>(rng()%10);++j)s[rng()%s.size()]=alphabet[rng()%alphabet.size()];
        data.push_back(s);
    }return data;
}
static vector<Provider> federation(const vector<string>& data,const Options& o) {
    vector<vector<pair<int,string>>> rows(o.m);std::mt19937_64 rng(o.seed);
    vector<int> membership;
    if(!o.assignment.empty()) {
        auto lines=load(o.assignment);
        if(lines.size()!=data.size())throw std::invalid_argument("assignment must contain exactly one provider ID per record");
        for(const auto& line:lines) {
            size_t consumed=0;int pid=std::stoi(line,&consumed);
            if(line.find_first_not_of(" \t",consumed)!=string::npos||pid<0||pid>=o.m)
                throw std::invalid_argument("invalid provider ID in assignment");
            membership.push_back(pid);
        }
    }
    vector<double> weight(o.m);for(int i=0;i<o.m;++i)weight[i]=std::pow(i+1,-o.skew);
    std::discrete_distribution<int> zipf(weight.begin(),weight.end());
    vector<int> indices(data.size());std::iota(indices.begin(),indices.end(),0);std::shuffle(indices.begin(),indices.end(),rng);
    for(int i:indices) {
        int pid=!membership.empty()?membership[i]:(o.split=="cluster"?i%8%o.m:zipf(rng));
        rows[pid].push_back({i,data[i]});
    }
    vector<Provider> ps;for(int i=0;i<o.m;++i)ps.emplace_back(i,std::move(rows[i]),o.backend,o.alpha);return ps;
}
static double recall(const vector<Item>& result,const vector<Item>& oracle) {
    if(oracle.empty())return 1;
    std::set<Item> keys(oracle.begin(),oracle.end());int common=0;
    for(auto& x:result)common+=keys.count(x);
    return static_cast<double>(common)/oracle.size();
}
static Options parse(int argc,char** argv) {
    Options o;
    for(int i=1;i<argc;++i) {
        string a=argv[i];if(a=="--self-test"){o.self_test=true;continue;}
        if(a=="--no-lb"){o.no_lb=true;continue;}
        if(a=="--help") {
            std::cout<<"--data FILE [--queries FILE] --out FILE --backend scan|minsearch|minsearch-certified\n"
                     <<"--m 8 --k 128 --num-queries 50 --repeats 3 --seed 42 --split zipf|cluster --skew 0.6\n"
                     <<"--kind dna|text --gram 1 --anchor 8 --alpha 2 --epsilon 1 --lambda .05 --rtt-ms 64\n"
                     <<"--algorithms baseline,dann,dann_star,fedseq_legacy,dann_order,fedseq,fedseq_star,fedseq_star_laplace,dann_order_star,fedseq_star_laplace_zero (subset)\n"
                     <<"--assignment FILE (one provider ID per record; sets split=fixed)\n"
                     <<"--privacy calibrated|nominal --noise-rng private|seeded (default calibrated/private)\n"
                     <<"--synthetic N --length 80 (smoke only), --self-test, --no-lb\n";std::exit(0);
        }
        if(i+1==argc)throw std::invalid_argument("missing value for "+a);
        string v=argv[++i];
        if(a=="--data")o.data=v;else if(a=="--queries")o.queries=v;else if(a=="--out")o.out=v;
        else if(a=="--assignment")o.assignment=v;
        else if(a=="--privacy")o.privacy=v;
        else if(a=="--noise-rng")o.noise_rng=v;
        else if(a=="--algorithms")o.algorithms=v;
        else if(a=="--backend")o.backend=v;else if(a=="--split")o.split=v;else if(a=="--kind")o.kind=v;
        else if(a=="--m")o.m=std::stoi(v);else if(a=="--k")o.k=std::stoi(v);
        else if(a=="--num-queries")o.num_queries=std::stoi(v);else if(a=="--repeats")o.repeats=std::stoi(v);
        else if(a=="--synthetic")o.synthetic=std::stoi(v);else if(a=="--length")o.length=std::stoi(v);
        else if(a=="--gram")o.gram=std::stoi(v);else if(a=="--anchor")o.anchor=std::stoi(v);
        else if(a=="--seed")o.seed=std::stoull(v);else if(a=="--skew")o.skew=std::stod(v);
        else if(a=="--epsilon")o.epsilon=std::stod(v);else if(a=="--lambda")o.lambda=std::stod(v);
        else if(a=="--rtt-ms")o.rtt=std::stod(v);else if(a=="--alpha")o.alpha=std::stod(v);
        else throw std::invalid_argument("unknown option: "+a);
    }
    if(o.m<1||o.k<1||o.num_queries<1||o.repeats<1||o.length<1||o.gram<1||o.anchor<0||o.synthetic<0||
       o.epsilon<=0||!std::isfinite(o.epsilon)||o.lambda<=0||o.lambda>=.5||!std::isfinite(o.lambda)||
       o.skew<0||!std::isfinite(o.skew)||o.alpha<=0||!std::isfinite(o.alpha)||o.rtt<0||!std::isfinite(o.rtt))
        throw std::invalid_argument("invalid numeric option");
    if(o.backend!="scan"&&o.backend!="minsearch"&&o.backend!="minsearch-certified")throw std::invalid_argument("invalid backend");
    if(!o.assignment.empty())o.split="fixed";
    if(o.split!="zipf"&&o.split!="cluster"&&o.split!="fixed")throw std::invalid_argument("invalid split");
    if(o.split=="fixed"&&o.assignment.empty())throw std::invalid_argument("fixed split requires --assignment FILE");
    if(o.kind!="dna"&&o.kind!="text")throw std::invalid_argument("invalid kind");
    if(o.privacy!="calibrated"&&o.privacy!="nominal")throw std::invalid_argument("privacy must be calibrated or nominal");
    if(o.noise_rng!="private"&&o.noise_rng!="seeded")throw std::invalid_argument("noise-rng must be private or seeded");
    std::stringstream selected(o.algorithms);string name;std::set<string> seen;
    while(std::getline(selected,name,',')) {
        if((name!="baseline"&&name!="dann"&&name!="dann_star"&&name!="fedseq"&&name!="fedseq_legacy"&&name!="dann_order"&&name!="fedseq_star"&&name!="fedseq_star_laplace"&&name!="dann_order_star"&&name!="fedseq_star_laplace_zero"&&name!="dann_gram2")||!seen.insert(name).second)
            throw std::invalid_argument("invalid or duplicate algorithm");
        if((name=="fedseq"||name=="fedseq_legacy"||name=="dann_order")&&o.backend!="scan")
            throw std::invalid_argument("FedSeq/order ablations currently require --backend scan");
    }
    if(seen.empty())throw std::invalid_argument("empty algorithms");
    return o;
}
static void require(bool value,const string& message) {if(!value)throw std::runtime_error("test failure: "+message);}
static void self_test();
#ifndef FEDKNN_NO_MAIN
int main(int argc,char** argv) {
    try {
        Options o=parse(argc,argv);configure(o);
        if(o.self_test){self_test();return 0;}
        if(o.data.empty()&&o.synthetic==0)throw std::invalid_argument("supply --data FILE or --synthetic N");
        auto data=o.synthetic?synthetic(o.synthetic,o.length,o.seed,o.kind):load(o.data);
        if(o.k>static_cast<int>(data.size()))throw std::invalid_argument("k exceeds database size");
        vector<string> queries;
        if(!o.queries.empty())queries=load(o.queries);
        else {
            vector<int> ids(data.size());std::iota(ids.begin(),ids.end(),0);std::mt19937_64 rng(o.seed+1);
            std::shuffle(ids.begin(),ids.end(),rng);
            for(int i=0;i<std::min(o.num_queries,static_cast<int>(ids.size()));++i)queries.push_back(data[ids[i]]);
        }
        if(static_cast<int>(queries.size())>o.num_queries)queries.resize(o.num_queries);
        auto t=Clock::now();double bc=process_cpu_ms();auto ps=federation(data,o);
        double build_cpu_ms=process_cpu_ms()-bc,build_ms=elapsed(t);
        std::ofstream f(o.out),fail(o.out+".failures.csv"),trace(o.out+".allocations.csv"),nodes(o.out+".nodes.csv");
        if(!f||!fail||!trace||!nodes)throw std::runtime_error("cannot write outputs: "+o.out);
        f<<std::setprecision(10);trace<<std::setprecision(10);nodes<<std::setprecision(10);
        f<<"dataset,backend,split,skew,m,k,epsilon,lambda,seed,query,repeat,algorithm,wall_ms,total_cpu_ms,provider_cpu_ms,broker_cpu_ms,provider_work_ms,broker_work_ms,parallel_compute_est_ms,modeled_e2e_ms,dp_calls,lb_evals,index_probes,cache_hits,first_quota,second_quota,unique_quota,lb_wire_records,result_wire_records,rounds,recall,exact_match,build_ms,build_cpu_ms,order_lb_enabled,order_lb_evals,lb_cpu_ms,order_lb_cpu_ms,zero_first,revived,dann_fallback,frontier_wire_records,privacy,noise_rng,beta1,beta2,distance_topk_valid\n";
        string allocation_header="algorithm,query,repeat,provider,clean_initial,first_request,actual_first,last_rank,clean_second_target,second_request,actual_second,oracle_contribution,first_noise,second_noise,offset,recall,second_offset\n";
        trace<<allocation_header;fail<<allocation_header;
        nodes<<"query,repeat,algorithm,provider,cpu_ms\n";
        vector<string> algorithms;string name;std::stringstream chosen(o.algorithms);
        while(std::getline(chosen,name,','))algorithms.push_back(name);
        std::map<string,std::array<double,5>> totals;std::mt19937_64 order_rng(o.seed+2);int failures=0;
        for(int qi=0;qi<static_cast<int>(queries.size());++qi) {
            Broker truth(ps,o.k,queries[qi],o.epsilon,o.lambda,o.rtt,o.seed);auto oracle=truth.oracle();
            for(auto& a:algorithms){Broker warm(ps,o.k,queries[qi],o.epsilon,o.lambda,o.rtt,o.seed,o.privacy=="calibrated",o.noise_rng=="private");warm.run(a,!o.no_lb);}
            for(int rep=0;rep<o.repeats;++rep) {
                auto shuffled=algorithms;std::shuffle(shuffled.begin(),shuffled.end(),order_rng);
                uint64_t noise_seed=o.seed+104729ULL*qi+1000003ULL*rep;
                for(auto& a:shuffled) {
                    Broker broker(ps,o.k,queries[qi],o.epsilon,o.lambda,o.rtt,noise_seed,o.privacy=="calibrated",o.noise_rng=="private");
                    auto run=broker.run(a,!o.no_lb);auto& x=run.metrics;
                    double rec=recall(run.result,oracle);bool exact=run.result==oracle;
                    bool distance_valid=run.result.size()==oracle.size();
                    for(size_t j=0;distance_valid&&j<oracle.size();++j)
                        distance_valid=run.result[j].distance==oracle[j].distance;
                    failures+=!exact;auto& total=totals[a];total[0]+=x.wall_ms;total[1]+=x.total_cpu_ms;
                    total[2]+=rec;total[3]+=!exact;total[4]+=x.dp_calls;
                    for(int pi=0;pi<o.m;++pi) {
                        auto z=run.allocations[pi];int needed=0;for(auto& item:oracle)needed+=item.provider==pi;
                        auto write_allocation=[&](std::ostream& out) {
                            out<<a<<','<<qi<<','<<rep<<','<<pi<<','<<z.initial<<','<<z.first<<','<<z.actual_first<<','<<z.rank<<','
                               <<z.target<<','<<z.second<<','<<z.actual_second<<','<<needed<<','<<z.first_laplace<<','<<z.second_laplace<<','<<z.offset<<','<<rec<<','<<z.second_offset<<'\n';
                        };
                        write_allocation(trace);if(!exact)write_allocation(fail);
                        nodes<<qi<<','<<rep<<','<<a<<','<<pi<<','<<x.provider_cpu_by_node[pi]<<'\n';
                    }
                    f<<(o.synthetic?"SYNTHETIC_SMOKE":"USER_DATA")<<','<<o.backend<<','<<o.split<<','<<o.skew<<','<<o.m<<','<<o.k<<','
                     <<o.epsilon<<','<<o.lambda<<','<<noise_seed<<','<<qi<<','<<rep<<','<<a<<','<<x.wall_ms<<','<<x.total_cpu_ms<<','
                     <<x.provider_cpu_ms<<','<<x.broker_cpu_ms<<','<<x.provider_work_ms<<','<<x.broker_work_ms<<','<<x.parallel_compute_est_ms<<','
                     <<x.modeled_e2e_ms<<','<<x.dp_calls<<','<<x.lb_evals<<','<<x.index_probes<<','<<x.cache_hits<<','<<x.first_quota<<','
                     <<x.second_quota<<','<<x.unique_quota<<','<<x.lb_wire_records<<','<<x.result_wire_records<<','<<x.rounds<<','
                     <<rec<<','<<exact<<','<<build_ms<<','<<build_cpu_ms<<','<<x.order_lb_enabled<<','<<x.order_lb_evals<<','<<x.lb_cpu_ms<<','<<x.order_lb_cpu_ms<<','<<x.zero_first<<','<<x.revived<<','<<x.dann_fallback<<','<<x.frontier_wire_records<<','<<o.privacy<<','<<o.noise_rng<<','<<(o.privacy=="calibrated"?o.epsilon/4:o.epsilon/2)<<','<<(o.privacy=="calibrated"?o.epsilon/(2.0*(o.k+o.m)):o.epsilon/2)<<','<<distance_valid<<'\n';
                }
            }
        }
        double n=queries.size()*o.repeats;
        std::cout<<"FEDSEQ_REVISED privacy="<<o.privacy<<" noise_rng="<<o.noise_rng<<" backend="<<o.backend<<" n="<<data.size()<<" queries="<<queries.size()<<" repeats="<<o.repeats
                 <<" build_ms="<<build_ms<<" build_cpu_ms="<<build_cpu_ms<<'\n';
        std::cout<<"algorithm mean_wall_ms mean_cpu_ms recall failed_runs mean_dp_calls\n";
        for(auto& v:totals)std::cout<<v.first<<' '<<v.second[0]/n<<' '<<v.second[1]/n<<' '<<v.second[2]/n<<' '<<v.second[3]<<' '<<v.second[4]/n<<'\n';
        std::cout<<"Serial algorithm reproduction, no SGX/obliviousness claim. CSV="<<o.out<<'\n';
        return failures?2:0;
    } catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
#endif

static void self_test() {
    long long checks=0;
    auto lcs=[](const string& a,const string& b) {
        vector<int> prev(b.size()+1),cur(b.size()+1);
        for(char c:a) {
            cur[0]=0;
            for(size_t j=0;j<b.size();++j)cur[j+1]=c==b[j]?prev[j]+1:std::max(prev[j+1],cur[j]);
            cur.swap(prev);
        }
        return prev.back();
    };
    std::mt19937_64 order_rng(17);
    for(int trial=0;trial<2000;++trial) {
        string a,b;
        int n=trial<9?vector<int>{0,1,63,64,65,127,128,129,256}[trial]:order_rng()%140;
        int m=order_rng()%170;
        for(int j=0;j<n;++j)a+=char(order_rng()%256);
        for(int j=0;j<m;++j)b+=char(order_rng()%256);
        int distance=edit_dp(a,b);OrderBound ob(a);
        int expected=n<=128?std::max(n,m)-lcs(a,b):std::abs(n-m);
        require(ob.lower(b)==expected,"order LB vs scalar LCS");
        require(ob.lower(b)<=distance,"order LB admissibility");checks+=2;
        for(int cut:{0,5,50,128}) {
            int v=ob.lower(b,cut);require(v<=distance,"order early certificate");
            require(v<=ob.lower(b),"early certificate <= full order LB");checks+=2;
        }
    }
    for(int width:{1,2,3}) {
        Options o;o.gram=width;o.kind="dna";configure(o);
        vector<string> strings={"","A","AC","AAA","ACGT","CACACA","ACACAC","NNNNN","ac?g","A\tC"};
        for(auto& a:strings)for(auto& b:strings) {
            int d=edit_dp(a,b);
            require(lower_bound_distance(calsig(a),a.size(),calsig(b),b.size())<=d,"LB admissibility");++checks;
            require(bigram_bound(bigrams(a),bigrams(b))<=d,"bigram LB admissibility");++checks;
            for(int cut=0;cut<=static_cast<int>(std::max(a.size(),b.size()))+1;++cut) {
                require(edit_dp(a,b,cut)==(d<=cut?d:-1),"bounded DP");++checks;
            }
        }
    }
    std::mt19937_64 rng(90125);int star_failed=0,star_runs=0;
    for(auto engine:{"scan","minsearch-certified"})for(int trial=0;trial<150;++trial) {
        Options o;o.backend=engine;o.kind=trial%2?"text":"dna";o.m=1+rng()%10;o.k=1+rng()%20;
        o.synthetic=30;o.skew=trial%2?.6:0;configure(o);
        auto data=synthetic(30,10+rng()%15,trial,o.kind);
        if(trial%5==0){data[0]="";data[1]="A";data[2]="AC";}
        if(trial%7==0)for(int j=10;j<30;++j)data[j]=data[j%10];
        auto ps=federation(data,o);string query=trial%3==0?data[trial%30]:"ACGTACGTACGT";
        Broker r(ps,o.k,query,1,.05,0,trial);auto oracle=r.oracle();
        for(auto name:{"baseline","dann","dann_star"})for(bool lb:{true,false}) {
            auto res=r.run(name,lb);
            if(string(name)!="dann_star")require(res.result==oracle,string(engine)+" "+name+" exactness");
            else {++star_runs;star_failed+=res.result!=oracle;}
            require(res.metrics.total_cpu_ms>=res.metrics.provider_cpu_ms&&res.metrics.broker_cpu_ms>=0,"CPU components");checks+=2;
            double sum=std::accumulate(res.metrics.provider_cpu_by_node.begin(),res.metrics.provider_cpu_by_node.end(),0.0);
            require(std::abs(sum-res.metrics.provider_cpu_ms)<1e-6,"provider CPU sum");++checks;
            for(auto& item:res.result) {
                require(item.id>=0&&item.id<static_cast<int>(data.size()),"dummy or invalid ID in result");
                require(item.distance==edit_dp(data[item.id],query),"distance result");checks+=2;
            }
            if(string(name)=="dann_star")require(res.metrics.result_wire_records==2LL*o.m*o.k,"two padded rounds");
            if(string(name)!="baseline") {
                for(auto& a:res.allocations) {
                    require(a.initial>=1,"paper must force at least one");
                    require(a.target==a.initial+o.k-(a.rank?a.rank:o.k),"paper clean map update");checks+=2;
                    if(string(name)=="dann_star") {
                        auto clipped=[&](double x){return x>=o.k?o.k:x<=1?1:static_cast<int>(std::ceil(x));};
                        require(a.first==clipped(a.initial+a.offset+a.first_laplace),"first Laplace quota");
                        require(a.second==clipped(a.target+a.second_offset+a.second_laplace),"second Laplace quota");checks+=2;
                    }
                }
            }
        }
        if(string(engine)=="scan")for(auto name:{"fedseq_legacy","dann_order","fedseq","dann_gram2"})for(bool lb:{true,false}) {
            auto res=r.run(name,lb);require(res.result==oracle,string(name)+" exactness");++checks;
            require(res.metrics.total_cpu_ms>=res.metrics.provider_cpu_ms,"FedSeq CPU components");++checks;
            bool stronger=string(name)!="fedseq_legacy"&&string(name)!="dann_gram2";
            require(res.metrics.order_lb_enabled==stronger,"order LB selection");++checks;
            if(string(name)!="dann_order"&&res.metrics.dann_fallback) {
                auto ref=r.run(stronger?"dann_order":"dann",lb);
                require(res.metrics.first_quota==ref.metrics.first_quota&&res.metrics.second_quota==ref.metrics.second_quota,"DANN fallback quota equality");
                require(res.metrics.dp_calls==ref.metrics.dp_calls,"DANN fallback distance calls");checks+=2;
            }
        }
    }
    int seq_star_failures=0,seq_star_runs=0;
    for(int trial=0;trial<120;++trial) {
        Options o;o.kind=trial%2?"text":"dna";o.m=1+rng()%8;o.k=1+rng()%20;configure(o);
        auto data=synthetic(32,20,trial,o.kind);auto ps=federation(data,o);
        double eps=trial%3==0?.001:trial%3==1?.1:2;
        Broker truth(ps,o.k,data[trial%32],eps,.05,0,trial);auto oracle=truth.oracle();
        for(auto name:{"fedseq_star","fedseq_star_laplace","dann_order_star","fedseq_star_laplace_zero"}) {
            Broker b(ps,o.k,data[trial%32],eps,.05,0,trial);auto res=b.run(name);
            ++seq_star_runs;seq_star_failures+=res.result!=oracle;
            require(res.metrics.result_wire_records==2LL*o.m*o.k,"new star fixed slots");++checks;
            for(auto& x:res.result) {require(x.distance==edit_dp(data[x.id],data[trial%32]),"new star real distances");++checks;}
            for(auto& a:res.allocations) {
                int floor=(string(name)=="fedseq_star"||string(name)=="fedseq_star_laplace_zero")?0:1;
                require(a.first>=floor&&a.first<=o.k&&a.second>=floor&&a.second<=o.k,"star request range");++checks;
                if(string(name)=="fedseq_star") {
                    require(a.first_laplace==std::floor(a.first_laplace)&&a.second_laplace==std::floor(a.second_laplace)&&a.offset==std::floor(a.offset),"integer geometric samples");++checks;
                }
            }
            Broker repeat(ps,o.k,data[trial%32],eps,.05,0,trial);auto again=repeat.run(name);
            require(again.result==res.result&&again.metrics.first_quota==res.metrics.first_quota&&again.metrics.second_quota==res.metrics.second_quota,"noise seed replay");++checks;
        }
    }
    // Independent distribution check: difference of two geometric RVs has
    // P(Z=0)=(1-a)/(1+a), Var(Z)=2a/(1-a)^2, and left shifted tail a^(eta+1)/(1+a).
    for(double eps:{.1,1.,2.}) {
        double e=eps/2,a=std::exp(-e),p=-std::expm1(-e);
        int eta=std::max(0,static_cast<int>(std::ceil(-std::log(.05*(1+a))/e))-1);
        std::geometric_distribution<long long> d(p);std::mt19937_64 gen(781);
        int zeros=0,negative_shift=0;double sum=0,sq=0;const int n=200000;
        for(int i=0;i<n;++i){auto x=d(gen),y=d(gen);double z=double(x)-double(y);zeros+=z==0;negative_shift+=z+eta<0;sum+=z;sq+=z*z;}
        double variance=2*a/(p*p),tail=std::pow(a,eta+1)/(1+a);
        require(std::abs(sum/n)<6*std::sqrt(variance/n),"geometric symmetry mean");
        require(std::abs(sq/n/variance-1)<.04,"geometric variance");
        require(std::abs(double(zeros)/n-p/(1+a))<.006,"geometric zero probability");
        require(std::abs(double(negative_shift)/n-tail)<.004&&tail<=.05+1e-12,"shifted geometric tail");checks+=4;
    }
    std::cout<<"STAR_TEST experimental_accuracy_failures="<<seq_star_failures<<'/'<<seq_star_runs<<'\n';
    // DANN must query the uncertain zero-origin node; no cold-node optimization here.
    Options c;configure(c);vector<Provider> uncertain;
    uncertain.emplace_back(0,vector<pair<int,string>>{{0,"CACACACACA"}},"scan",2);
    uncertain.emplace_back(1,vector<pair<int,string>>{{1,"ACACACACAG"}},"scan",2);
    Broker r(uncertain,1,"ACACACACAC",1,.05,0,42);auto oracle=r.oracle();auto dann=r.run("dann");
    require(dann.result==oracle&&dann.metrics.first_quota==2,"DANN forced-one counterexample");++checks;
    auto seq=r.run("fedseq_legacy");
    require(seq.result==oracle&&seq.metrics.zero_first==1&&seq.metrics.revived==1,"uncertain cold node revived");++checks;
    require(r.run("fedseq").result==oracle,"order LB cold example");++checks;
    // A truly irrelevant cold node may stay asleep; stable ties and empty nodes.
    vector<Provider> cold;
    cold.emplace_back(0,vector<pair<int,string>>{{0,"AAAA"},{1,"AAAA"}},"scan",2);
    cold.emplace_back(1,vector<pair<int,string>>{{2,"TTTT"}},"scan",2);
    cold.emplace_back(2,vector<pair<int,string>>{},"scan",2);
    Broker cr(cold,2,"AAAA",1,.05,0,42);auto cold_truth=cr.oracle();
    for(auto name:{"fedseq_legacy","fedseq"}) {
        auto res=cr.run(name);require(res.result==cold_truth,"cold ties exactness");
        require(res.metrics.revived==0&&res.allocations[1].second==0,"certified cold stays asleep");checks+=2;
    }
    TopK unique(3);unique.insert({1,0,1});unique.insert({1,0,1});require(unique.values().size()==1,"result ID dedup");++checks;
    std::cout<<"PASS checks="<<checks<<" random_federations=300 DANN_star_accuracy_failures="<<star_failed<<'/'<<star_runs<<'\n';
}
