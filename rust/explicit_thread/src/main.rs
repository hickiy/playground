mod short_run;
fn main() {
    multiple_thread_sort();
}

fn multiple_thread_sort() {
    let arr = [1, 25, -4, 10, 100];
    let max = short_run::find_max(&arr).unwrap();
    println!("The max element is {}", max);
}
