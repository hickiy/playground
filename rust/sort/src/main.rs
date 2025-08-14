fn main() {
    vec_sort();
    flot_sort();
    struct_sort();
}

fn vec_sort() {
    let mut vec = vec![1, 5, 10, 2, 15];
    vec.sort();
    println!("{:?}", vec);
}

fn flot_sort() {
    let mut vec = vec![1.1, 1.15, 5.5, 1.123, 2.0];
    vec.sort_by(|a, b| a.partial_cmp(b).unwrap());
    println!("{:?}", vec);
}

fn struct_sort() {
    #[derive(Debug, Eq, Ord, PartialEq, PartialOrd)]
    struct Person {
        name: String,
        age: u32,
    }

    impl Person {
        fn new(name: String, age: u32) -> Self {
            Person { name, age }
        }
    }

    let mut people = vec![
        Person::new("Zoe".to_string(), 25),
        Person::new("Al".to_string(), 60),
        Person::new("John".to_string(), 1),
    ];

    people.sort();

    println!("{:?}", people);

    people.sort_by(|a,b| b.age.cmp(&a.age));

    println!("{:?}", people);
}
