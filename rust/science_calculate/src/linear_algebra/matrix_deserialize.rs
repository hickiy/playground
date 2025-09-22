use nalgebra::DMatrix;
use serde_json;

pub fn main() -> Result<(), std::io::Error> {
    let row_slice: Vec<i32> = (1..5).collect();
    let matrix = DMatrix::from_row_slice(1, 4, &row_slice);
    println!("Original Matrix:\n{}", matrix);

    // 序列化矩阵
    let serialized_matrix = serde_json::to_string(&matrix)?;
    println!("Serialized Matrix: {}", serialized_matrix);

    // 反序列化出矩阵
    let deserialized_matrix: DMatrix<i32> = serde_json::from_str(&serialized_matrix)?;
    println!("Deserialized Matrix:\n{}", deserialized_matrix);
    Ok(())
}
