#include "edit.h"



int edit_dp(const string& s1, const string& s2)
{
	const size_t len1 = s1.size(), len2 = s2.size();
	vector< int> col(len2 + 1), prevCol(len2 + 1);

	for (size_t i = 0; i < prevCol.size(); i++)
		prevCol[i] = static_cast<int>(i);
	for (size_t i = 0; i < len1; i++) {
		col[0] = static_cast<int>(i + 1);
		for (size_t j = 0; j < len2; j++)
			col[j + 1] = min({ prevCol[1 + j] + 1, col[j] + 1, prevCol[j] + (s1[i] == s2[j] ? 0 : 1) });
		col.swap(prevCol);
	}
	return prevCol[len2];
	return 0;
}

// Safe banded DP: -1 means distance exceeds k; no padded-buffer/SIMD assumptions.
int edit_dp(const string& s1, const string& s2, const int k)
{
    if (k < 0) return -1;
    const int n = static_cast<int>(s1.size()), m = static_cast<int>(s2.size());
    if (abs(n-m) > k) return -1;
    if (k >= max(n,m)) return edit_dp(s1,s2);
    const int inf = k+1;
    vector<int> prev(m+1, inf), cur(m+1, inf);
    for (int j=0; j<=min(m,k); ++j) prev[j]=j;
    for (int i=1; i<=n; ++i) {
        int lo=max(1,i-k), hi=min(m,i+k);
        cur[0] = i<=k ? i : inf;
        if (lo>1) cur[lo-1]=inf;
        for (int j=lo; j<=hi; ++j)
            cur[j]=min({inf,prev[j]+1,cur[j-1]+1,prev[j-1]+(s1[i-1]!=s2[j-1])});
        if (hi<m) cur[hi+1]=inf;
        cur.swap(prev);
    }
    return prev[m]<=k ? prev[m] : -1;
}

#ifdef __linux__

int slide(const char *x, const char *y)
// computes slide of x and y - returns the index of the first disagreement
// x and y should be zero terminted plus there should be 7 characters afterwards that are different for x and y
// the procedure assumes little-endian memory layout for integers (intel x86 type). 
// For big-endian one would need to modify the computation using __builtin_ctz to something using __builtin_clz    
{
	int i=0;

	//	printf("(%s,%s,",x,y);

	while (*((int64*)x) == *((int64*)y)){ x += 8; y += 8; i += 8; }		// find the first 8-bytes that differ

	//	printf("%i --- %lx --- (%i) ",i,(*((int64*)x)-*((int64*)y)), __builtin_ctz(*((int64*)x)-*((int64*)y)));	

	i += (__builtin_ctzll(*((int64*)x) - *((int64*)y)) >> 3);	// calculates the first byte of the 8 that differs

	//	printf("%i) ",i);

	return i;
}

int slide32(const char *x, const char *y)
// computes slide of x and y - returns the index of the first disagreement
// x and y should be zero terminted plus there should be 7 characters afterwards that are different for x and y
// the procedure assumes little-endian memory layout for integers (intel x86 type). 
// For big-endian one would need to modify the computation using __builtin_ctz to something using __builtin_clz    
{
	int i = 0;

	//	printf("(%s,%s,",x,y);

	while (*((int32*)x) == *((int32*)y)){ x += 4; y += 4; i += 4; }		// find the first 8-bytes that differ

	//	printf("%i --- %lx --- (%i) ",i,(*((int32*)x)-*((int32*)y)), __builtin_ctz(*((int32*)x)-*((int32*)y)));	

	i += (__builtin_ctz(*((int32*)x) - *((int32*)y)) >> 3);	// calculates the first byte of the 8 that differs

	//	printf("%i) ",i);

	return i;
}


int edit_dp(const char *x, const int x_len, const  char *y, const int y_len, int k)
// computes the edit distance of x and y
// x and y should be zero terminated plus there should be 7 characters afterwards that are different for x and y
// (we don't really need zero termination but we need 8 characters after x and y that differ)
{
	if (k >= K)return -1;			// error - too large k

	if (x_len > y_len)return edit_dp(y, y_len, x, x_len, k);

	int fc_buf[2 * K + 1], fp_buf[2 * K + 1];        // must be at least 2k+3
	int *fc, *fp;				// current F(d,h) and previous F(d,h-1)
	int h, dl, du, d;

	fc_buf[K] = fp_buf[K] = -1;

	for (h = 0; h <= k; h++){

		if ((h & 1) == 0){ fc = fc_buf + K; fp = fp_buf + K; }
		else{ fc = fp_buf + K; fp = fc_buf + K; }

		dl = -min(1 + ((k - (y_len - x_len)) / 2), h);	// compute the range of relevant diagonals
		du = min(1 + k / 2 + (y_len - x_len), h);

		fp[dl - 1] = fp[dl] = fp[du] = fp[du + 1] = -1;

		for (d = dl; d <= du; d++){
			int r = max(max(fp[d - 1], fp[d] + 1), fp[d + 1] + 1);

			if ((r >= x_len) || (r + d >= y_len))fc[d] = r;
			else fc[d] = r + slide(x + r, y + r + d);

			if ((d == y_len - x_len) && (fc[d] >= x_len))return h;
		}
	}
	return -1;
}

#endif
