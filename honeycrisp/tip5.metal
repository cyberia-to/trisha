// Tip5 hash function for Neptune PoW mining on Apple Silicon.
//
// Goldilocks field: p = 2^64 - 2^32 + 1 = 0xFFFFFFFF00000001.
// Elements stored as Montgomery form: raw_u64() == a * R mod p, R = 2^64.
// Since 2^64 ≡ 2^32-1 (mod p), we have R = 0xFFFFFFFF.
//
// Constants mds_column[16] and round_consts[80] are injected by the Rust
// caller as Metal constant buffers (buffer indices 5 and 6).

#include <metal_stdlib>
using namespace metal;

// ── Goldilocks constants ──────────────────────────────────────────────────────

constant ulong GL_P      = 0xFFFFFFFF00000001UL;
constant ulong MONTY_ONE = 0x00000000FFFFFFFFUL;  // 1 * R mod p = 2^32 - 1

// ── Field arithmetic ─────────────────────────────────────────────────────────

static ulong gl_add(ulong a, ulong b) {
    ulong s = a + b;
    bool carry = s < a;
    if (carry || s >= GL_P) s -= GL_P;
    return s;
}

static ulong gl_sub(ulong a, ulong b) {
    ulong d = a - b;
    if (a < b) d += GL_P;
    return d;
}

// 64×64 → 128-bit product via four 32×32 products.
static ulong2 mul128(ulong a, ulong b) {
    uint a0 = (uint)a,         a1 = (uint)(a >> 32);
    uint b0 = (uint)b,         b1 = (uint)(b >> 32);
    ulong p00 = (ulong)a0 * b0;
    ulong p01 = (ulong)a0 * b1;
    ulong p10 = (ulong)a1 * b0;
    ulong p11 = (ulong)a1 * b1;
    ulong cross = p01 + p10;
    ulong cross_carry = (cross < p01) ? 1UL : 0UL;
    ulong lo = p00 + (cross << 32);
    ulong lo_carry  = (lo  < p00)   ? 1UL : 0UL;
    ulong hi = p11 + (cross >> 32) + (cross_carry << 32) + lo_carry;
    return ulong2(lo, hi);
}

// Montgomery reduction: montyred(xl, xh) = (xl + xh*2^64) * R^{-1} mod p.
// Matches BFieldElement::montyred exactly.
static ulong montyred(ulong xl, ulong xh) {
    ulong shifted = xl << 32;
    ulong a       = xl + shifted;
    ulong e       = (a < xl) ? 1UL : 0UL;
    ulong b       = a - (a >> 32) - e;
    ulong r       = xh - b;
    ulong c       = (xh < b) ? 1UL : 0UL;
    return r - (0xFFFFFFFFUL * c);
}

static ulong gl_mul(ulong a, ulong b) {
    ulong2 p = mul128(a, b);
    return montyred(p.x, p.y);
}

// Convert Montgomery form to canonical u64.
static ulong to_canonical(ulong x) {
    return montyred(x, 0UL);
}

// Convert canonical u64 to Montgomery form: x → x * R mod p.
// montyred(x * R2) where R2 = R^2 mod p = 0xFFFFFFFE00000001.
static ulong gl_new(ulong x) {
    ulong R2 = 0xFFFFFFFE00000001UL;
    ulong2 p = mul128(x, R2);
    return montyred(p.x, p.y);
}

// x^7 in Montgomery form: x * x^2 * x^4.
static ulong gl_pow7(ulong x) {
    ulong x2 = gl_mul(x, x);
    ulong x4 = gl_mul(x2, x2);
    return gl_mul(x, gl_mul(x2, x4));
}

// ── Tip5 lookup table (S-box for elements 0..4) ───────────────────────────────

constant uchar LOOKUP_TABLE[256] = {
    0, 7, 26, 63, 124, 215, 85, 254, 214, 228, 45, 185, 140, 173, 33, 240,
    29, 177, 176, 32, 8, 110, 87, 202, 204, 99, 150, 106, 230, 14, 235, 128,
    213, 239, 212, 138, 23, 130, 208, 6, 44, 71, 93, 116, 146, 189, 251, 81,
    199, 97, 38, 28, 73, 179, 95, 84, 152, 48, 35, 119, 49, 88, 242, 3, 148,
    169, 72, 120, 62, 161, 166, 83, 175, 191, 137, 19, 100, 129, 112, 55, 221,
    102, 218, 61, 151, 237, 68, 164, 17, 147, 46, 234, 203, 216, 22, 141, 65,
    57, 123, 12, 244, 54, 219, 231, 96, 77, 180, 154, 5, 253, 133, 165, 98,
    195, 205, 134, 245, 30, 9, 188, 59, 142, 186, 197, 181, 144, 92, 31, 224,
    163, 111, 74, 58, 69, 113, 196, 67, 246, 225, 10, 121, 50, 60, 157, 90,
    122, 2, 250, 101, 75, 178, 159, 24, 36, 201, 11, 243, 132, 198, 190, 114,
    233, 39, 52, 21, 209, 108, 238, 91, 187, 18, 104, 194, 37, 153, 34, 200,
    143, 126, 155, 236, 118, 64, 80, 172, 89, 94, 193, 135, 183, 86, 107, 252,
    13, 167, 206, 136, 220, 207, 103, 171, 160, 76, 182, 227, 217, 158, 56, 174,
    4, 66, 109, 139, 162, 184, 211, 249, 47, 125, 232, 117, 43, 16, 42, 127,
    20, 241, 25, 149, 105, 156, 51, 53, 168, 145, 247, 223, 79, 78, 226, 15,
    222, 82, 115, 70, 210, 27, 41, 1, 170, 40, 131, 192, 229, 248, 255
};

static ulong sbox_lookup(ulong x) {
    uchar4 lo = as_type<uchar4>((uint)x);
    uchar4 hi = as_type<uchar4>((uint)(x >> 32));
    lo = uchar4(LOOKUP_TABLE[lo[0]], LOOKUP_TABLE[lo[1]], LOOKUP_TABLE[lo[2]], LOOKUP_TABLE[lo[3]]);
    hi = uchar4(LOOKUP_TABLE[hi[0]], LOOKUP_TABLE[hi[1]], LOOKUP_TABLE[hi[2]], LOOKUP_TABLE[hi[3]]);
    return (ulong)as_type<uint>(lo) | ((ulong)as_type<uint>(hi) << 32);
}

// ── Tip5 permutation ──────────────────────────────────────────────────────────

static void tip5_permute(thread ulong* state,
                         constant ulong* mds,
                         constant ulong* rc) {
    for (int round = 0; round < 5; round++) {
        // S-box: lookup for elements 0..4, x^7 for 4..16
        for (int i = 0; i < 4;  i++) state[i] = sbox_lookup(state[i]);
        for (int i = 4; i < 16; i++) state[i] = gl_pow7(state[i]);

        // Circulant MDS: new[row] = sum_col mds[(row-col)&15] * state[col].
        // Inner loop fully unrolled so state[col] accesses are compile-time constants
        // (allowing register allocation) and mds[] accesses go to constant cache.
        ulong ns[16];
        for (int row = 0; row < 16; row++) {
            ulong acc;
            acc  =                gl_mul(mds[(row -  0) & 15], state[ 0]);
            acc  = gl_add(acc,    gl_mul(mds[(row -  1) & 15], state[ 1]));
            acc  = gl_add(acc,    gl_mul(mds[(row -  2) & 15], state[ 2]));
            acc  = gl_add(acc,    gl_mul(mds[(row -  3) & 15], state[ 3]));
            acc  = gl_add(acc,    gl_mul(mds[(row -  4) & 15], state[ 4]));
            acc  = gl_add(acc,    gl_mul(mds[(row -  5) & 15], state[ 5]));
            acc  = gl_add(acc,    gl_mul(mds[(row -  6) & 15], state[ 6]));
            acc  = gl_add(acc,    gl_mul(mds[(row -  7) & 15], state[ 7]));
            acc  = gl_add(acc,    gl_mul(mds[(row -  8) & 15], state[ 8]));
            acc  = gl_add(acc,    gl_mul(mds[(row -  9) & 15], state[ 9]));
            acc  = gl_add(acc,    gl_mul(mds[(row - 10) & 15], state[10]));
            acc  = gl_add(acc,    gl_mul(mds[(row - 11) & 15], state[11]));
            acc  = gl_add(acc,    gl_mul(mds[(row - 12) & 15], state[12]));
            acc  = gl_add(acc,    gl_mul(mds[(row - 13) & 15], state[13]));
            acc  = gl_add(acc,    gl_mul(mds[(row - 14) & 15], state[14]));
            acc  = gl_add(acc,    gl_mul(mds[(row - 15) & 15], state[15]));
            ns[row] = acc;
        }
        for (int i = 0; i < 16; i++) state[i] = ns[i];

        // Add round constants
        int base = round * 16;
        for (int i = 0; i < 16; i++) state[i] = gl_add(state[i], rc[base + i]);
    }
}

// ── Sponge operations ─────────────────────────────────────────────────────────

// hash_pair(left[5], right[5]) → out[5]. FixedLength domain: capacity = MONTY_ONE.
static void hash_pair(thread ulong* out,
                      thread const ulong* left,
                      thread const ulong* right,
                      constant ulong* mds,
                      constant ulong* rc) {
    ulong state[16];
    for (int i = 0; i < 5;  i++) state[i]     = left[i];
    for (int i = 0; i < 5;  i++) state[5 + i] = right[i];
    for (int i = 10; i < 16; i++) state[i]    = MONTY_ONE;
    tip5_permute(state, mds, rc);
    for (int i = 0; i < 5; i++) out[i] = state[i];
}

// hash_varlen for the 300-BFE NeptunePow.encode() input.
// Layout: nonce[5] || path_b[145 zeros] || path_a[145] || root[5 zeros].
// Only nonce and path_a are variable; the rest are zero.
static void hash_varlen_pow(thread ulong* out,
                             thread const ulong* nonce,    // 5 elements
                             constant ulong* path_a,       // 145 elements
                             constant ulong* mds,
                             constant ulong* rc) {
    ulong state[16] = {};  // VariableLength: all zeros

    // Chunk 0: nonce[5] + path_b[0..5] (zeros)
    for (int i = 0; i < 5;  i++) state[i] = nonce[i];
    for (int i = 5; i < 10; i++) state[i] = 0;
    tip5_permute(state, mds, rc);

    // Chunks 1..14: path_b[5..145] = all zeros (14 chunks)
    for (int chunk = 0; chunk < 14; chunk++) {
        for (int i = 0; i < 10; i++) state[i] = 0;
        tip5_permute(state, mds, rc);
    }

    // Chunks 15..28: path_a[0..140] (14 chunks of 10)
    for (int chunk = 0; chunk < 14; chunk++) {
        for (int i = 0; i < 10; i++) state[i] = path_a[chunk * 10 + i];
        tip5_permute(state, mds, rc);
    }

    // Chunk 29: path_a[140..145] + root[0..5] (zeros)
    for (int i = 0; i < 5; i++) state[i]     = path_a[140 + i];
    for (int i = 5; i < 10; i++) state[i]    = 0;
    tip5_permute(state, mds, rc);

    // Padding block (remainder = 0, so padding = [ONE, zeros...])
    state[0] = MONTY_ONE;
    for (int i = 1; i < 10; i++) state[i] = 0;
    tip5_permute(state, mds, rc);

    for (int i = 0; i < 5; i++) out[i] = state[i];
}

// hash_varlen for 5-element input (used in fast_mast_hash for intermediate digests).
static void hash_varlen_5(thread ulong* out,
                           thread const ulong* inp,
                           constant ulong* mds,
                           constant ulong* rc) {
    ulong state[16] = {};  // VariableLength: all zeros
    // Remainder = 5: state[0..5] = inp, state[5] = ONE, state[6..10] = 0
    for (int i = 0; i < 5; i++) state[i]  = inp[i];
    state[5] = MONTY_ONE;
    for (int i = 6; i < 10; i++) state[i] = 0;
    tip5_permute(state, mds, rc);
    for (int i = 0; i < 5; i++) out[i] = state[i];
}

// ── fast_mast_hash ────────────────────────────────────────────────────────────
//
// Mirrors PowMastPaths::fast_mast_hash from neptune_mine.rs.
// mast_paths layout: [pow[3] * 5, header[2] * 5, kernel[1] * 5] = 30 u64s.

// mast is 30 u64s in threadgroup memory: pow[3]*5 + header[2]*5 + kernel[1]*5.
// Each 5-element digest is copied to a thread-local temp before hash_pair so
// all pointer arguments share the same (thread) address space.
static void fast_mast_hash(thread ulong* result,
                             thread const ulong* nonce,
                             constant ulong* path_a,
                             threadgroup const ulong* mast,
                             constant ulong* mds,
                             constant ulong* rc) {
    ulong h[5], tmp[5], p[5];

    hash_varlen_pow(h, nonce, path_a, mds, rc);

    for (int i = 0; i < 5; i++) p[i] = mast[i];      hash_pair(tmp, h,   p, mds, rc);
    for (int i = 0; i < 5; i++) p[i] = mast[5+i];    hash_pair(h, tmp,   p, mds, rc);
    for (int i = 0; i < 5; i++) p[i] = mast[10+i];   hash_pair(tmp, p,   h, mds, rc);
    hash_varlen_5(h, tmp, mds, rc);
    for (int i = 0; i < 5; i++) p[i] = mast[15+i];   hash_pair(tmp, h,   p, mds, rc);
    for (int i = 0; i < 5; i++) p[i] = mast[20+i];   hash_pair(h, tmp,   p, mds, rc);
    hash_varlen_5(tmp, h, mds, rc);
    for (int i = 0; i < 5; i++) p[i] = mast[25+i];   hash_pair(result, tmp, p, mds, rc);
}

// ── Digest comparison ─────────────────────────────────────────────────────────
//
// Matches Digest::cmp in twenty-first: reverse-order comparison of canonical values.

static bool digest_le(thread const ulong* a, constant ulong* b) {
    for (int i = 4; i >= 0; i--) {
        ulong av = to_canonical(a[i]);
        ulong bv = b[i];
        if (av < bv) return true;
        if (av > bv) return false;
    }
    return true;  // equal counts as <=
}

// ── Mining kernel ─────────────────────────────────────────────────────────────
//
// Buffer bindings point into the merged Rust-side `BlockTemplate` and
// `MineState` allocations (via offsets) — restoring the original 7-buffer
// signature avoided a ~3-4× kernel slowdown observed when accessing fields
// through `constant BlockTemplate*` references (MSL compiler appears to
// generate worse code for struct-pointer field access than for direct
// `constant ulong*` arguments). Layout of those structs is documented in
// `types.rs`; this kernel sees raw u64 arrays.

kernel void npt_mine(
    constant ulong*       path_a     [[buffer(0)]],   // BlockTemplate offset 0   : 145 u64s
    constant ulong*       mast_paths [[buffer(1)]],   // BlockTemplate offset 1160: 30 u64s
    constant ulong*       target     [[buffer(2)]],   // BlockTemplate offset 1400: 5 u64s canonical
    device   atomic_uint* found      [[buffer(3)]],   // MineState     offset 0   : u32 flag
    device   ulong*       result     [[buffer(4)]],   // MineState     offset 8   : attempt + nonce[5]
    constant ulong*       mds_column [[buffer(5)]],   // 16 u64s
    constant ulong*       round_cs   [[buffer(6)]],   // 80 u64s
    constant ulong*       nonce_range [[buffer(7)]],
    uint                  tid        [[thread_index_in_threadgroup]],
    uint                  gid        [[thread_position_in_grid]]
) {
    threadgroup ulong tg_mast[30];
    if (tid < 30) tg_mast[tid] = mast_paths[tid];
    threadgroup_barrier(mem_flags::mem_threadgroup);

    if (ulong(gid) >= nonce_range[1]) return;

    ulong attempt = nonce_range[0] + gid;
    ulong nonce_bfe[5];
    nonce_bfe[0] = gl_new(attempt);
    nonce_bfe[1] = gl_new(attempt ^ 0xA5A5A5A5A5A5A5A5UL);
    nonce_bfe[2] = gl_new(attempt * 6364136223846793005UL);
    nonce_bfe[3] = gl_new((attempt << 32) | (attempt >> 32));
    nonce_bfe[4] = gl_new(attempt + 1442695040888963407UL);

    ulong digest[5];
    fast_mast_hash(digest, nonce_bfe, path_a, tg_mast, mds_column, round_cs);

    if (!digest_le(digest, target)) return;

    uint expected = 0;
    bool won = false;
    do {
        won = atomic_compare_exchange_weak_explicit(found, &expected, 1u,
            memory_order_relaxed, memory_order_relaxed);
    } while (!won && expected == 0);
    if (won) {
        result[0] = attempt;
        for (int i = 0; i < 5; i++) result[i + 1] = nonce_bfe[i];
    }
}
