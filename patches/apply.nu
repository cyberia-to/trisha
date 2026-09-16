#!/usr/bin/env nu
#
# Fetch triton-vm + twenty-first from crates.io and apply GPU acceleration overlay.
#
# No .patch files — just Rust code and surgical str replace.
# Each replacement has a named step so you see what's happening.
#
# Usage: nu patches/apply.nu
# Result: .vendor/triton-vm/ and .vendor/twenty-first/ ready to build with GPU hooks.

let tv_version = "7.0.0"
let tf_version = "1.1.0"
let project_root = ($env.FILE_PWD | path join "..")

cd $project_root

# ── Helper: fetch a crate from registry ─────────────────────────

def fetch_crate [name: string, version: string, vendor_dir: string] {
    ^python3 -B patches/fetch.py $name $version $vendor_dir
    if $env.LAST_EXIT_CODE != 0 { error make {msg: $"verified upstream fetch failed: ($name) ($version)"} }
}

# ── Fetch upstream crates ───────────────────────────────────────

mkdir .vendor

print $"Fetching twenty-first ($tf_version)..."
fetch_crate "twenty-first" $tf_version ".vendor/twenty-first"

print $"Fetching triton-vm ($tv_version)..."
fetch_crate "triton-vm" $tv_version ".vendor/triton-vm"

# The compiler family is part of the same pinned source input.
for name in [triton-air triton-isa triton-constraint-circuit triton-constraint-builder] {
    print $"Fetching ($name) ($tv_version)..."
    fetch_crate $name $tv_version $".vendor/($name)"
}

# triton-vm's twenty-first dep is redirected by [patch.crates-io] in Cargo.toml

# ══════════════════════════════════════════════════════════════════
# TWENTY-FIRST PATCHES
# ══════════════════════════════════════════════════════════════════

print "  [T0] twenty-first and triton-vm: hashed Rust library outputs"

# Multi-crate-type targets use an unversioned rlib output name. Reusing that
# output with another lockfile can mix serde/rand/number type identities.
# These tools require Rust libraries only; no C ABI is shipped.
for name in [twenty-first triton-vm] {
    let manifest = $".vendor/($name)/Cargo.toml"
    let original = (open --raw $manifest)
    let anchor = "crate-type = [\n    \"cdylib\",\n    \"rlib\",\n]"
    if not ($original | str contains $anchor) { error make {msg: $"review changed library crate types: ($name)"} }
    $original | str replace $anchor 'crate-type = ["rlib"]' | save -f $manifest
}

print "  [T1] twenty-first: MerkleTree::from_nodes constructor"

let mt_file = ".vendor/twenty-first/src/util_types/merkle_tree.rs"
(open $mt_file
    | str replace ('    pub fn par_new(leafs: &[Digest]) -> Result<Self>') ('    /// Construct a MerkleTree from a pre-computed flat node array.
    ///
    /// The caller is responsible for ensuring the nodes are valid
    /// (root at index 1, leaves at [n..2n), all internal nodes correct).
    /// Used by GPU-accelerated tree construction.
    pub fn from_nodes(nodes: Vec<Digest>) -> Self {
        MerkleTree { nodes }
    }

    pub fn par_new(leafs: &[Digest]) -> Result<Self>')
    | save -f $mt_file)

# ══════════════════════════════════════════════════════════════════
# TRITON-VM PATCHES
# ══════════════════════════════════════════════════════════════════

# ── Layer 0: gpu.rs — the trait itself ──────────────────────────

print "  [0] gpu.rs — GpuAccelerator trait"
cp patches/gpu.rs .vendor/triton-vm/src/gpu.rs

# ── Layer 1: lib.rs — export the module ─────────────────────────

print "  [1] lib.rs — pub mod gpu"
let lib_rs = ".vendor/triton-vm/src/lib.rs"
(open $lib_rs | str replace
    "pub mod fri;\n"
    "pub mod fri;\npub mod gpu;\n"
    | save -f $lib_rs)

# ── Layer 2: visibility — open internal types ───────────────────

print "  [2] visibility — pub(crate) → pub"

let stark = ".vendor/triton-vm/src/stark.rs"
(open $stark
    | str replace "pub(crate) struct ProverDomains" "pub struct ProverDomains"
    | str replace "pub(crate) fn randomized_trace_len" "pub fn randomized_trace_len"
    | str replace "pub(crate) fn interpolant_degree" "pub fn interpolant_degree"
    | save -f $stark)

let aux = ".vendor/triton-vm/src/table/auxiliary_table.rs"
(open $aux
    | str replace "pub(crate) struct DegreeWithOrigin" "pub struct DegreeWithOrigin"
    | save -f $aux)

let mt = ".vendor/triton-vm/src/table/master_table.rs"
(open $mt
    | str replace "pub(crate) trait BfeSlice" "pub trait BfeSlice"
    | str replace "pub(crate) trait MasterTable" "pub trait MasterTable"
    | str replace "    pub(crate) fn new(\n        aet: &AlgebraicExecutionTrace," "    pub fn new(\n        aet: &AlgebraicExecutionTrace,"
    | str replace "    pub(crate) fn try_to_main_row" "    pub fn try_to_main_row"
    | str replace "    pub(crate) fn try_to_aux_row" "    pub fn try_to_aux_row"
    | str replace "pub(crate) fn max_degree_with_origin" "pub fn max_degree_with_origin"
    | save -f $mt)

# ── Layer 3: hash dispatch — GPU Tip5 batch hashing ────────────

print "  [3] hash dispatch — Tip5 batch hashing"

(open $stark
    | str replace "use crate::fri;\n" "use crate::fri;\nuse crate::gpu;\n"
    | str replace ('        profiler!(start "hash rows of quotient segments" ("hash"));
        let interpret_xfe_as_bfes = |xfe: &XFieldElement| xfe.coefficients.to_vec();
        let hash_row = |row: ArrayView1<_>| {
            let row_as_bfes = row.iter().map(interpret_xfe_as_bfes).concat();
            Tip5::hash_varlen(&row_as_bfes)
        };
        let quotient_segments_rows = fri_domain_quotient_segment_codewords
            .axis_iter(ROW_AXIS)
            .into_par_iter();
        let fri_domain_quotient_segment_codewords_digests =
            quotient_segments_rows.map(hash_row).collect::<Vec<_>>();
        profiler!(stop "hash rows of quotient segments");') ('        profiler!(start "hash rows of quotient segments" ("hash"));
        let interpret_xfe_as_bfes = |xfe: &XFieldElement| xfe.coefficients.to_vec();
        let fri_domain_quotient_segment_codewords_digests =
            if let Some(gpu) = gpu::gpu_accelerator() {
                let rows: Vec<Vec<BFieldElement>> = fri_domain_quotient_segment_codewords
                    .axis_iter(ROW_AXIS)
                    .map(|row| row.iter().flat_map(interpret_xfe_as_bfes).collect())
                    .collect();
                let row_refs: Vec<&[BFieldElement]> =
                    rows.iter().map(|r| r.as_slice()).collect();
                gpu.hash_varlen_batch(&row_refs)
            } else {
                let hash_row = |row: ArrayView1<_>| {
                    let row_as_bfes = row.iter().map(interpret_xfe_as_bfes).concat();
                    Tip5::hash_varlen(&row_as_bfes)
                };
                fri_domain_quotient_segment_codewords
                    .axis_iter(ROW_AXIS)
                    .into_par_iter()
                    .map(hash_row)
                    .collect::<Vec<_>>()
            };
        profiler!(stop "hash rows of quotient segments");')
    | save -f $stark)

(open $mt
    | str replace "use crate::challenges::Challenges;\n" "use crate::challenges::Challenges;\nuse crate::gpu;\n"
    | str replace ('            let all_digests = fri_domain_table
                .axis_iter(ROW_AXIS)
                .into_par_iter()
                .map(|row| row.to_slice().unwrap())
                .map(Self::Field::bfe_slice)
                .map(Tip5::hash_varlen)
                .collect();') ('            let all_digests = if let Some(gpu) = gpu::gpu_accelerator() {
                let rows: Vec<Vec<BFieldElement>> = fri_domain_table
                    .axis_iter(ROW_AXIS)
                    .map(|row| {
                        let slice = row.to_slice().unwrap();
                        Self::Field::bfe_slice(slice).to_vec()
                    })
                    .collect();
                let row_refs: Vec<&[BFieldElement]> = rows.iter().map(|r| r.as_slice()).collect();
                gpu.hash_varlen_batch(&row_refs)
            } else {
                fri_domain_table
                    .axis_iter(ROW_AXIS)
                    .into_par_iter()
                    .map(|row| row.to_slice().unwrap())
                    .map(Self::Field::bfe_slice)
                    .map(Tip5::hash_varlen)
                    .collect()
            };')
    | save -f $mt)

# ── Layer 4: iNTT dispatch — GPU polynomial interpolation ──────

print "  [4] iNTT dispatch — polynomial interpolation"

(open $stark
    | str replace ('        profiler!(start "poly interpolate" ("LDE"));
        main_table
            .trace_table_mut()
            .axis_iter_mut(COL_AXIS)
            .into_par_iter()
            .for_each(|mut column| intt(column.as_slice_mut().unwrap()));
        aux_table
            .trace_table_mut()
            .axis_iter_mut(COL_AXIS)
            .into_par_iter()
            .for_each(|mut column| intt(column.as_slice_mut().unwrap()));
        profiler!(stop "poly interpolate");') ('        profiler!(start "poly interpolate" ("LDE"));
        if let Some(gpu) = gpu::gpu_accelerator() {
            {
                let mut trace = main_table.trace_table_mut();
                let ncols = trace.ncols();
                for c in 0..ncols {
                    let col_slice = trace.column_mut(c).into_slice_memory_order().unwrap();
                    gpu.intt_bfe(col_slice);
                }
            }
            {
                let mut trace = aux_table.trace_table_mut();
                let ncols = trace.ncols();
                for c in 0..ncols {
                    let col_slice = trace.column_mut(c).into_slice_memory_order().unwrap();
                    gpu.intt_xfe(col_slice);
                }
            }
        } else {
            main_table
                .trace_table_mut()
                .axis_iter_mut(COL_AXIS)
                .into_par_iter()
                .for_each(|mut column| intt(column.as_slice_mut().unwrap()));
            aux_table
                .trace_table_mut()
                .axis_iter_mut(COL_AXIS)
                .into_par_iter()
                .for_each(|mut column| intt(column.as_slice_mut().unwrap()));
        }
        profiler!(stop "poly interpolate");')
    | save -f $stark)

# ── Layer 5: Merkle tree dispatch — GPU tree construction ───────

print "  [5] Merkle tree dispatch — GPU tree construction"

# master_table.rs: replace MerkleTree::par_new with GPU dispatch
(open $mt
    | str replace ('        profiler!(start "Merkle tree" ("hash"));
        let merkle_tree = MerkleTree::par_new(&hashed_rows).unwrap();
        profiler!(stop "Merkle tree");') ('        profiler!(start "Merkle tree" ("hash"));
        let merkle_tree = if let Some(gpu) = gpu::gpu_accelerator() {
            gpu.merkle_tree(&hashed_rows)
        } else {
            MerkleTree::par_new(&hashed_rows).unwrap()
        };
        profiler!(stop "Merkle tree");')
    | save -f $mt)

# stark.rs: replace quotient MerkleTree::par_new with GPU dispatch
(open $stark
    | str replace ('        let quot_merkle_tree = MerkleTree::par_new(&fri_domain_quotient_segment_codewords_digests)?;') ('        let quot_merkle_tree = if let Some(gpu) = gpu::gpu_accelerator() {
            gpu.merkle_tree(&fri_domain_quotient_segment_codewords_digests)
        } else {
            MerkleTree::par_new(&fri_domain_quotient_segment_codewords_digests)?
        };')
    | save -f $stark)

# ── Layer 6: FRI fold dispatch — GPU split-and-fold ─────────────

print "  [6] FRI fold dispatch — GPU split-and-fold"

let fri_rs = ".vendor/triton-vm/src/fri.rs"
(open $fri_rs
    | str replace "use crate::profiler::profiler;\n" "use crate::gpu;\nuse crate::profiler::profiler;\n"
    | str replace ('    fn split_and_fold(&self, folding_challenge: XFieldElement) -> Vec<XFieldElement> {
        let one = xfe!(1);
        let two_inverse = xfe!(2).inverse();

        let domain_points = self.domain.values();
        let domain_point_inverses = BFieldElement::batch_inversion(domain_points);

        let n = self.codeword.len();
        (0..n / 2)
            .into_par_iter()
            .map(|i| {
                let scaled_offset_inv = folding_challenge * domain_point_inverses[i];
                let left_summand = (one + scaled_offset_inv) * self.codeword[i];
                let right_summand = (one - scaled_offset_inv) * self.codeword[n / 2 + i];
                (left_summand + right_summand) * two_inverse
            })
            .collect()
    }') ('    fn split_and_fold(&self, folding_challenge: XFieldElement) -> Vec<XFieldElement> {
        let domain_points = self.domain.values();
        let domain_point_inverses = BFieldElement::batch_inversion(domain_points);

        if let Some(gpu) = gpu::gpu_accelerator() {
            return gpu.fri_fold(&self.codeword, &domain_point_inverses, folding_challenge);
        }

        let one = xfe!(1);
        let two_inverse = xfe!(2).inverse();

        let n = self.codeword.len();
        (0..n / 2)
            .into_par_iter()
            .map(|i| {
                let scaled_offset_inv = folding_challenge * domain_point_inverses[i];
                let left_summand = (one + scaled_offset_inv) * self.codeword[i];
                let right_summand = (one - scaled_offset_inv) * self.codeword[n / 2 + i];
                (left_summand + right_summand) * two_inverse
            })
            .collect()
    }')
    | save -f $fri_rs)

# ── Layer 7: Forward NTT dispatch — GPU "restore original trace" ──

print "  [7] Forward NTT dispatch — restore original trace"

(open $stark
    | str replace ('        profiler!(start "restore original trace" ("LDE"));
        main_table
            .trace_table_mut()
            .axis_iter_mut(COL_AXIS)
            .into_par_iter()
            .for_each(|mut column| ntt(column.as_slice_mut().unwrap()));
        aux_table
            .trace_table_mut()
            .axis_iter_mut(COL_AXIS)
            .into_par_iter()
            .for_each(|mut column| ntt(column.as_slice_mut().unwrap()));
        profiler!(stop "restore original trace");') ('        profiler!(start "restore original trace" ("LDE"));
        if let Some(gpu) = gpu::gpu_accelerator() {
            {
                let mut trace = main_table.trace_table_mut();
                let ncols = trace.ncols();
                for c in 0..ncols {
                    let col_slice = trace.column_mut(c).into_slice_memory_order().unwrap();
                    gpu.ntt_bfe(col_slice);
                }
            }
            {
                let mut trace = aux_table.trace_table_mut();
                let ncols = trace.ncols();
                for c in 0..ncols {
                    let col_slice = trace.column_mut(c).into_slice_memory_order().unwrap();
                    gpu.ntt_xfe(col_slice);
                }
            }
        } else {
            main_table
                .trace_table_mut()
                .axis_iter_mut(COL_AXIS)
                .into_par_iter()
                .for_each(|mut column| ntt(column.as_slice_mut().unwrap()));
            aux_table
                .trace_table_mut()
                .axis_iter_mut(COL_AXIS)
                .into_par_iter()
                .for_each(|mut column| ntt(column.as_slice_mut().unwrap()));
        }
        profiler!(stop "restore original trace");')
    | save -f $stark)

# ── Layer 8: GEMV dispatch — GPU weighted sum of columns ─────────

print "  [8] GEMV dispatch — weighted_sum_of_columns"

(open $mt
    | str replace ('        let weighted_sum_of_trace_columns = self
            .trace_table()
            .axis_iter(ROW_AXIS)
            .into_par_iter()
            .map(|row| row.iter().zip_eq(&weights).map(|(&r, &w)| r * w).sum())
            .collect::<Vec<_>>();') ('        let weighted_sum_of_trace_columns = if let Some(gpu) = gpu::gpu_accelerator() {
            use std::any::TypeId;
            let trace = self.trace_table();
            let nrows = trace.nrows();
            let ncols = trace.ncols();
            let weights_slice = weights.as_slice().unwrap();

            if TypeId::of::<Self::Field>() == TypeId::of::<BFieldElement>() {
                // Trace is column-major: gather into row-major flat buffer for GPU.
                let mut flat = vec![BFieldElement::ZERO; nrows * ncols];
                for c in 0..ncols {
                    let col = trace.column(c);
                    let col_slice = col.as_slice().unwrap();
                    // SAFETY: TypeId confirms Self::Field == BFieldElement
                    let bfe_col: &[BFieldElement] = unsafe {
                        std::slice::from_raw_parts(
                            col_slice.as_ptr() as *const BFieldElement,
                            col_slice.len(),
                        )
                    };
                    for r in 0..nrows {
                        flat[r * ncols + c] = bfe_col[r];
                    }
                }
                gpu.gemv_bfe(&flat, nrows, ncols, weights_slice)
            } else if TypeId::of::<Self::Field>() == TypeId::of::<XFieldElement>() {
                let mut flat = vec![XFieldElement::zero(); nrows * ncols];
                for c in 0..ncols {
                    let col = trace.column(c);
                    let col_slice = col.as_slice().unwrap();
                    let xfe_col: &[XFieldElement] = unsafe {
                        std::slice::from_raw_parts(
                            col_slice.as_ptr() as *const XFieldElement,
                            col_slice.len(),
                        )
                    };
                    for r in 0..nrows {
                        flat[r * ncols + c] = xfe_col[r];
                    }
                }
                gpu.gemv_xfe(&flat, nrows, ncols, weights_slice)
            } else {
                trace
                    .axis_iter(ROW_AXIS)
                    .into_par_iter()
                    .map(|row| row.iter().zip_eq(&weights).map(|(&r, &w)| r * w).sum())
                    .collect::<Vec<_>>()
            }
        } else {
            self
            .trace_table()
            .axis_iter(ROW_AXIS)
            .into_par_iter()
            .map(|row| row.iter().zip_eq(&weights).map(|(&r, &w)| r * w).sum())
            .collect::<Vec<_>>()
        };')
    | save -f $mt)


# Version-pinned upstream warning fixes. Fail if an upstream anchor changes.
def exact_patch [file: path, before: string, after: string] {
    let source = (open --raw $file)
    if not ($source | str contains $before) { error make {msg: $"missing upstream patch anchor in ($file): ($before)"} }
    $source | str replace $before $after | save --force $file
}
print "  [9] explicit crate reexports and Copy metadata"
exact_patch $lib_rs 'pub use isa;' 'pub use ::isa;'
exact_patch $lib_rs 'pub use twenty_first;' 'pub use ::twenty_first;'
exact_patch $aux '#[derive(Debug, Clone, Eq, PartialEq, Ord, PartialOrd)]' '#[derive(Debug, Clone, Copy, Eq, PartialEq, Ord, PartialOrd)]'

nu patches/tasm.nu
if $env.LAST_EXIT_CODE != 0 { error make {msg: "recursive verifier bootstrap failed"} }

print "Done. GPU overlay and pinned upstream fixes applied to .vendor/"
