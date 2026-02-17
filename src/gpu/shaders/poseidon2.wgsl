// Poseidon2 hash permutation over Goldilocks field.
//
// State width: 16 field elements (Tip5-compatible).
// Used for Merkle tree construction in STARK proving.
// Each workgroup hashes one node. Tree is built level-by-level
// from leaves to root.
//
// Round structure:
//   - Full rounds (beginning): apply S-box to all 16 elements
//   - Partial rounds (middle): apply S-box to element 0 only
//   - Full rounds (end): apply S-box to all 16 elements
//   - Linear layer (MDS matrix) after each round

// Import Goldilocks arithmetic
// fn gl_add(a: vec2<u32>, b: vec2<u32>) -> vec2<u32>
// fn gl_mul(a: vec2<u32>, b: vec2<u32>) -> vec2<u32>

const STATE_WIDTH: u32 = 16u;
const FULL_ROUNDS_BEGIN: u32 = 4u;
const PARTIAL_ROUNDS: u32 = 22u;
const FULL_ROUNDS_END: u32 = 4u;
const TOTAL_ROUNDS: u32 = 30u;  // 4 + 22 + 4
const DIGEST_LEN: u32 = 5u;

struct HashParams {
    n_nodes: u32,       // Number of nodes to hash in this dispatch
    level: u32,         // Tree level (0 = leaves)
    _pad0: u32,
    _pad1: u32,
}

// Round constants: TOTAL_ROUNDS * STATE_WIDTH field elements
@group(0) @binding(0) var<storage, read> round_constants: array<vec2<u32>>;
// MDS matrix: STATE_WIDTH * STATE_WIDTH field elements
@group(0) @binding(1) var<storage, read> mds_matrix: array<vec2<u32>>;
// Input: leaf data or child hashes
@group(0) @binding(2) var<storage, read> input: array<vec2<u32>>;
// Output: parent hashes (DIGEST_LEN elements per node)
@group(0) @binding(3) var<storage, read_write> output: array<vec2<u32>>;
@group(0) @binding(4) var<uniform> params: HashParams;

// S-box: x^7 (Goldilocks-compatible power map)
fn sbox(x: vec2<u32>) -> vec2<u32> {
    let x2 = gl_mul(x, x);
    let x4 = gl_mul(x2, x2);
    let x3 = gl_mul(x2, x);
    return gl_mul(x4, x3);
}

// Apply MDS matrix to state
fn apply_mds(state: ptr<function, array<vec2<u32>, 16>>) {
    var new_state: array<vec2<u32>, 16>;
    for (var i = 0u; i < STATE_WIDTH; i = i + 1u) {
        var acc = vec2<u32>(0u, 0u);
        for (var j = 0u; j < STATE_WIDTH; j = j + 1u) {
            let m = mds_matrix[i * STATE_WIDTH + j];
            acc = gl_add(acc, gl_mul(m, (*state)[j]));
        }
        new_state[i] = acc;
    }
    for (var i = 0u; i < STATE_WIDTH; i = i + 1u) {
        (*state)[i] = new_state[i];
    }
}

// Add round constants to state
fn add_constants(state: ptr<function, array<vec2<u32>, 16>>, round: u32) {
    let base = round * STATE_WIDTH;
    for (var i = 0u; i < STATE_WIDTH; i = i + 1u) {
        (*state)[i] = gl_add((*state)[i], round_constants[base + i]);
    }
}

// Full Poseidon2 permutation
fn poseidon2_permute(state: ptr<function, array<vec2<u32>, 16>>) {
    var round = 0u;

    // Full rounds (beginning)
    for (var r = 0u; r < FULL_ROUNDS_BEGIN; r = r + 1u) {
        add_constants(state, round);
        for (var i = 0u; i < STATE_WIDTH; i = i + 1u) {
            (*state)[i] = sbox((*state)[i]);
        }
        apply_mds(state);
        round = round + 1u;
    }

    // Partial rounds
    for (var r = 0u; r < PARTIAL_ROUNDS; r = r + 1u) {
        add_constants(state, round);
        (*state)[0] = sbox((*state)[0]);
        apply_mds(state);
        round = round + 1u;
    }

    // Full rounds (end)
    for (var r = 0u; r < FULL_ROUNDS_END; r = r + 1u) {
        add_constants(state, round);
        for (var i = 0u; i < STATE_WIDTH; i = i + 1u) {
            (*state)[i] = sbox((*state)[i]);
        }
        apply_mds(state);
        round = round + 1u;
    }
}

@compute @workgroup_size(64)
fn hash_merkle_node(@builtin(global_invocation_id) gid: vec3<u32>) {
    let node_idx = gid.x;
    if node_idx >= params.n_nodes {
        return;
    }

    // Load state: two child digests (2 * DIGEST_LEN = 10 elements)
    // padded to STATE_WIDTH with zeros
    var state: array<vec2<u32>, 16>;
    let child_base = node_idx * 2u * DIGEST_LEN;
    for (var i = 0u; i < 2u * DIGEST_LEN; i = i + 1u) {
        state[i] = input[child_base + i];
    }
    for (var i = 2u * DIGEST_LEN; i < STATE_WIDTH; i = i + 1u) {
        state[i] = vec2<u32>(0u, 0u);
    }

    // Permute
    poseidon2_permute(&state);

    // Extract digest (first DIGEST_LEN elements)
    let out_base = node_idx * DIGEST_LEN;
    for (var i = 0u; i < DIGEST_LEN; i = i + 1u) {
        output[out_base + i] = state[i];
    }
}
