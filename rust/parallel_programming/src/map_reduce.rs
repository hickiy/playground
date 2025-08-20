use rayon::prelude::*;

pub fn new() {
    struct Person {
        age: u32,
    }
    let v: Vec<Person> = vec![
        Person { age: 23 },
        Person { age: 19 },
        Person { age: 42 },
        Person { age: 17 },
        Person { age: 17 },
        Person { age: 31 },
        Person { age: 30 },
    ];

    let num_over_30 = v.par_iter().filter(|&x| x.age >= 30).count() as f32;
    let sum_over_32 = v
        .par_iter()
        .map(|x| x.age)
        .filter(|x| *x >= 30)
        .reduce(|| 0, |x, y| x + y);

    let avg_over_30 = sum_over_32 as f32 / num_over_30;

    println!("The average age of people older then 30 is {}", avg_over_30);
}
