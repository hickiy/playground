use crossbeam;
use crossbeam_channel::bounded;
use std::thread;
use std::time::Duration;

pub fn new() {
    let (snd1, rcv1) = bounded::<i32>(1);
    let (snd2, rcv2) = bounded::<i32>(1);
    let n_msgs = 4;
    let n_workers = 2;
    crossbeam::scope(|s| {
        // 生产者线程
        s.spawn(|_| {
            for i in 0..n_msgs {
                snd1.send(i).unwrap();
                println!("Source sent {}", i);
            }
            drop(snd1);
        });
        
        // 由 2 个线程并行处理
        for _ in 0..n_workers {
            let (sendr, recvr) = (snd2.clone(), rcv1.clone());
            // 在不同的线程中衍生工人
            s.spawn(move |_| {
                thread::sleep(Duration::from_millis(500));
                // 接收数据，直到信道关闭前
                for msg in recvr.iter() {
                    println!("Worker {:?} received {}.", thread::current().id(), msg);
                    sendr.send(msg * 2).unwrap();
                }
            });
        }
        // 关闭信道，否则接收器不会关闭
        // 退出 for 循坏
        drop(snd2);

        // 接收器
        for msg in rcv2.iter() {
            println!("Sink received {}", msg);
        }
    })
    .unwrap();
}
