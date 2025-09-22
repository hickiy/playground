#![allow(dead_code)]
mod matrix_addition;
mod matrix_deserialize;
mod matrix_inversion;
mod matrix_multiplication;
mod matrix_multiplication2;
mod vector_comparison;
mod vector_norm;

fn main() {
    // matrix_addition::main();
    // matrix_multiplication::main();
    // matrix_multiplication2::main();
    // vector_comparison::main();
    // vector_norm::main();
    // matrix_inversion::main();
    matrix_deserialize::main().unwrap();
}
