// FRI (Fast Reed-Solomon Interactive Oracle Proof) query evaluation.
//
// Parallel evaluation of FRI folding queries. Each invocation handles
// one query point: fold the polynomial at a random challenge, verify
// the Merkle authentication path.
//
// Used in both proving (commit to FRI layers) and verification
// (check FRI queries against commitments).

// Import Goldilocks arithmetic
// fn gl_add(a: vec2<u32>, b: vec2<u32>) -> vec2<u32>
// fn gl_sub(a: vec2<u32>, b: vec2<u32>) -> vec2<u32>
// fn gl_mul(a: vec2<u32>, b: vec2<u32>) -> vec2<u32>
// fn gl_inv(a: vec2<u32>) -> vec2<u32>

struct FriParams {
    n_queries: u32,       // Number of FRI queries
    domain_size: u32,     // Current domain size
    _pad0: u32,
    _pad1: u32,
}

// Polynomial evaluations at query points (paired: f(x), f(-x))
@group(0) @binding(0) var<storage, read> evaluations: array<vec2<u32>>;
// FRI folding challenge (alpha)
@group(0) @binding(1) var<storage, read> challenge: vec2<u32>;
// Domain elements (evaluation points)
@group(0) @binding(2) var<storage, read> domain: array<vec2<u32>>;
// Output: folded evaluations
@group(0) @binding(3) var<storage, read_write> folded: array<vec2<u32>>;
@group(0) @binding(4) var<uniform> params: FriParams;

// FRI fold: given f(x) and f(-x), compute the folded value
// fold(alpha) = (f(x) + f(-x)) / 2 + alpha * (f(x) - f(-x)) / (2*x)
@compute @workgroup_size(64)
fn fri_fold(@builtin(global_invocation_id) gid: vec3<u32>) {
    let query_idx = gid.x;
    if query_idx >= params.n_queries {
        return;
    }

    let fx = evaluations[query_idx * 2u];
    let fnx = evaluations[query_idx * 2u + 1u];
    let x = domain[query_idx];
    let alpha = challenge;

    // even = (f(x) + f(-x)) / 2
    let sum = gl_add(fx, fnx);
    let two = vec2<u32>(2u, 0u);
    let two_inv = gl_inv(two);
    let even = gl_mul(sum, two_inv);

    // odd = (f(x) - f(-x)) / (2*x)
    let diff = gl_sub(fx, fnx);
    let two_x = gl_mul(two, x);
    let two_x_inv = gl_inv(two_x);
    let odd = gl_mul(diff, two_x_inv);

    // folded = even + alpha * odd
    folded[query_idx] = gl_add(even, gl_mul(alpha, odd));
}

// Batch FRI verification: check multiple queries against a commitment.
// Each query checks that the folded evaluation matches the committed
// Merkle leaf value.
@compute @workgroup_size(64)
fn fri_verify_query(@builtin(global_invocation_id) gid: vec3<u32>) {
    let query_idx = gid.x;
    if query_idx >= params.n_queries {
        return;
    }

    // The folded value should match the next layer's evaluation
    // at the corresponding index. The host checks Merkle paths;
    // this shader handles the algebraic folding.
    let expected = evaluations[query_idx];
    let computed = folded[query_idx];

    // Write match result: 1 if equal, 0 if mismatch
    if expected.x == computed.x && expected.y == computed.y {
        folded[query_idx] = vec2<u32>(1u, 0u);
    } else {
        folded[query_idx] = vec2<u32>(0u, 0u);
    }
}
