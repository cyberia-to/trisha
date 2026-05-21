// Number Theoretic Transform (NTT) over Goldilocks field.
//
// Radix-2 Cooley-Tukey butterfly. Each workgroup processes one
// butterfly layer. Twiddle factors are precomputed on CPU and
// uploaded as a storage buffer.
//
// Usage: dispatch ceil(n/2 / workgroup_size) workgroups per layer,
// iterate over log2(n) layers on the host side.

// Import Goldilocks arithmetic (included by the host at compile time)
// fn gl_add(a: vec2<u32>, b: vec2<u32>) -> vec2<u32>
// fn gl_sub(a: vec2<u32>, b: vec2<u32>) -> vec2<u32>
// fn gl_mul(a: vec2<u32>, b: vec2<u32>) -> vec2<u32>

struct NttParams {
    n: u32,           // Transform length (power of 2)
    layer: u32,       // Current butterfly layer (0..log2(n)-1)
    _pad0: u32,
    _pad1: u32,
}

@group(0) @binding(0) var<storage, read_write> data: array<vec2<u32>>;
@group(0) @binding(1) var<storage, read> twiddles: array<vec2<u32>>;
@group(0) @binding(2) var<uniform> params: NttParams;

@compute @workgroup_size(64)
fn ntt_butterfly(@builtin(global_invocation_id) gid: vec3<u32>) {
    let idx = gid.x;
    let half_block = 1u << params.layer;
    let block_size = half_block << 1u;
    let n_butterflies = params.n >> 1u;

    if idx >= n_butterflies {
        return;
    }

    // Determine which butterfly within which block
    let block_idx = idx / half_block;
    let pos_in_block = idx % half_block;
    let top = block_idx * block_size + pos_in_block;
    let bot = top + half_block;

    // Twiddle factor index
    let tw_idx = pos_in_block * (params.n / block_size);

    let a = data[top];
    let b = data[bot];
    let tw = twiddles[tw_idx];

    // Butterfly: top' = a + tw*b, bot' = a - tw*b
    let tb = gl_mul(tw, b);
    data[top] = gl_add(a, tb);
    data[bot] = gl_sub(a, tb);
}

// Inverse NTT: same butterfly structure but with inverse twiddles
// and final multiplication by 1/n. The host provides inverse twiddles
// in the twiddles buffer and dispatches a separate normalization pass.

@compute @workgroup_size(64)
fn ntt_normalize(@builtin(global_invocation_id) gid: vec3<u32>) {
    let idx = gid.x;
    if idx >= params.n {
        return;
    }

    // n_inv = inverse of n in Goldilocks field (precomputed as twiddles[0])
    let n_inv = twiddles[0];
    data[idx] = gl_mul(data[idx], n_inv);
}
