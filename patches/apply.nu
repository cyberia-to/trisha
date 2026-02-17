#!/usr/bin/env nu
#
# Fetch triton-vm from crates.io and apply GPU acceleration overlay.
#
# No .patch files — just Rust code and surgical str replace.
# Each replacement has a named step so you see what's happening.
#
# Usage: nu patches/apply.nu
# Result: .vendor/triton-vm/ ready to build with GPU hooks.

let version = "2.0.0"
let vendor_dir = ".vendor/triton-vm"
let project_root = ($env.FILE_PWD | path join "..")

cd $project_root

# ── Fetch upstream ──────────────────────────────────────────────

rm -rf $vendor_dir
mkdir .vendor

print $"Fetching triton-vm ($version)..."

let cargo_home = ($env | get -o CARGO_HOME | default $"($env.HOME)/.cargo")
let registry_src = $"($cargo_home)/registry/src"
let crate_name = $"triton-vm-($version)"

let cached = (glob $"($registry_src)/**/($crate_name)" | first)

if ($cached | is-empty) {
    print "Not in cache, downloading via cargo..."
    let tmp = (mktemp -d)
    $"[package]\nname = \"fetch-triton-vm\"\nversion = \"0.0.0\"\nedition = \"2021\"\n\n[dependencies]\ntriton-vm = \"=($version)\"\n" | save $"($tmp)/Cargo.toml"
    mkdir $"($tmp)/src"
    "" | save $"($tmp)/src/lib.rs"
    cd $tmp; cargo fetch; cd $project_root
    rm -rf $tmp

    let cached = (glob $"($registry_src)/**/($crate_name)" | first)
    if ($cached | is-empty) {
        error make { msg: $"failed to download triton-vm ($version)" }
    }
}

print $"Found: ($cached)"
cp -r $cached $vendor_dir

# ── Layer 0: gpu.rs — the trait itself ──────────────────────────

print "  [0] gpu.rs — GpuAccelerator trait"
cp patches/gpu.rs $"($vendor_dir)/src/gpu.rs"

# ── Layer 1: lib.rs — export the module ─────────────────────────

print "  [1] lib.rs — pub mod gpu"
let lib_rs = $"($vendor_dir)/src/lib.rs"
(open $lib_rs | str replace
    "pub mod fri;\n"
    "pub mod fri;\npub mod gpu;\n"
    | save -f $lib_rs)

# ── Layer 2: visibility — open internal types ───────────────────

print "  [2] visibility — pub(crate) → pub"

# stark.rs
let stark = $"($vendor_dir)/src/stark.rs"
(open $stark
    | str replace "pub(crate) struct ProverDomains" "pub struct ProverDomains"
    | str replace "pub(crate) fn randomized_trace_len" "pub fn randomized_trace_len"
    | str replace "pub(crate) fn interpolant_degree" "pub fn interpolant_degree"
    | save -f $stark)

# auxiliary_table.rs
let aux = $"($vendor_dir)/src/table/auxiliary_table.rs"
(open $aux
    | str replace "pub(crate) struct DegreeWithOrigin" "pub struct DegreeWithOrigin"
    | save -f $aux)

# master_table.rs
let mt = $"($vendor_dir)/src/table/master_table.rs"
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

# stark.rs: add gpu import + replace quotient hash block
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

# master_table.rs: add gpu import + replace FRI domain hash block
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

print $"Done. GPU overlay applied to ($vendor_dir)"
