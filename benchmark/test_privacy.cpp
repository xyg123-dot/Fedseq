#define FEDKNN_NO_MAIN
#include "fedknn_benchmark.cpp"

// Enumerate record-replacement neighbors and common first histories. This is
// a regression check for the analytic bounds, not a replacement for the proof.
int main(int, char**) {
    Options options;options.kind="dna";configure(options);
    const vector<string> vocabulary={"AA","AC","CA","CC"};
    long long checks=0;int max_first=0,max_second_dann=0,max_second_seq=0;
    auto vectors=[&](const vector<string>& data,const string& alg,const vector<int>& h,int m,int k) {
        vector<vector<pair<int,string>>> rows(m);
        for(size_t i=0;i<data.size();++i)rows[i%static_cast<size_t>(m)].push_back({static_cast<int>(i),data[i]});
        vector<Provider> ps;for(int i=0;i<m;++i)ps.emplace_back(i,rows[i],"scan",2);
        Broker broker(ps,k,"AC",1,.05,0,7);
        auto run=broker.run(alg,true,&h);vector<int> a,b;
        for(auto& x:run.allocations){a.push_back(x.initial);b.push_back(x.target);}
        return std::make_pair(a,b);
    };
    auto compare=[&](const vector<string>& d,const vector<string>& neighbor,const vector<int>& h,int m,int k) {
        for(const string& alg:{string("dann_star"),string("fedseq_star")}) {
            auto a=vectors(d,alg,h,m,k),b=vectors(neighbor,alg,h,m,k);int delta1=0,delta2=0;
            for(int j=0;j<m;++j){delta1+=std::abs(a.first[j]-b.first[j]);delta2+=std::abs(a.second[j]-b.second[j]);}
            require(delta1<=2,"first-vector sensitivity");
            require(delta2<=k+m,"conditional second-vector sensitivity");
            max_first=std::max(max_first,delta1);
            if(alg=="dann_star")max_second_dann=std::max(max_second_dann,delta2);
            else max_second_seq=std::max(max_second_seq,delta2);
            checks+=2;
        }
    };
    for(int mask=0;mask<256;++mask) {
        vector<string> d;int z=mask;for(int i=0;i<4;++i){d.push_back(vocabulary[z%4]);z/=4;}
        for(int h0=0;h0<=2;++h0)for(int h1=0;h1<=2;++h1)
            for(int at=0;at<4;++at)for(auto& value:vocabulary)if(value!=d[at]) {
                auto neighbor=d;neighbor[at]=value;compare(d,neighbor,{h0,h1},2,2);
            }
    }
    std::mt19937_64 rng(20261014);
    for(int trial=0;trial<2000;++trial) {
        int m=1+rng()%6,k=1+rng()%6;vector<string>d(12);
        for(auto& s:d)for(int j=0;j<1+int(rng()%12);++j)s+="ACGT"[rng()%4];
        auto neighbor=d;int at=rng()%d.size();neighbor[at]="";
        for(int j=0;j<int(rng()%15);++j)neighbor[at]+="ACGT"[rng()%4];
        vector<int> h(m);for(int& x:h)x=rng()%(k+1);
        compare(d,neighbor,h,m,k);
    }
    std::cout<<"PASS sensitivity_checks="<<checks<<" exhaustive_datasets=256 histories_per_dataset=9"
             <<" random_neighbors=2000 max_delta1="<<max_first
             <<" max_delta2_dann="<<max_second_dann<<" max_delta2_fedseq="<<max_second_seq<<'\n';
}
