use crossbeam_channel::unbounded;
use std::{thread, time};
pub fn new() {
    let (snd, rcv) = unbounded::<i32>();
    let n_msgs = 5;
    crossbeam::scope(|s| {
        s.spawn(|_| {
            for i in 0..n_msgs {
                snd.send(i).unwrap();
                thread::sleep(time::Duration::from_millis(1000));
            }
        });

        for _ in 0..n_msgs {
            let msg = rcv.recv().unwrap();
            println!("Received {}", msg)
        }
    })
    .unwrap();
    println!("main thread ended");
}
