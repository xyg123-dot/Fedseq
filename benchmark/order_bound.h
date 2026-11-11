#pragma once
#include <array>
#include <string>
#include <algorithm>
// Classical LCS bound, exact byte equality. No novelty claim.
// Supports query <=128 bytes on GCC/Clang; safely returns length bound otherwise.
class OrderBound {
 size_t n;
#if defined(__SIZEOF_INT128__)
 using Bits=__uint128_t;std::array<Bits,256> masks{};
#endif
public:
 explicit OrderBound(const std::string&q):n(q.size()){
#if defined(__SIZEOF_INT128__)
 if(n<=128)for(size_t i=0;i<n;++i)masks[(unsigned char)q[i]]|=Bits(1)<<i;
#endif
 }
 int lower(const std::string&s,int cutoff=-1)const{
#if defined(__SIZEOF_INT128__)
 if(n<=128){Bits state=0;size_t seen=0;for(unsigned char c:s){Bits x=masks[c]|state;Bits y=(state<<1)|1;state=x&~(x-y);++seen;
   if(cutoff>=0&&seen%16==0){int partial=__builtin_popcountll((unsigned long long)state)+__builtin_popcountll((unsigned long long)(state>>64));int upper=std::min(n,size_t(partial)+s.size()-seen);int certificate=int(std::max(n,s.size()))-upper;if(certificate>cutoff)return certificate;}}
  int lcs=__builtin_popcountll((unsigned long long)state)+__builtin_popcountll((unsigned long long)(state>>64));return int(std::max(n,s.size()))-lcs;}
#endif
 return std::abs(int(n)-int(s.size()));
 }
};
