use std::io::{BufRead, BufReader, Error};
use std::net::{Ipv4Addr, SocketAddrV4, TcpListener};

fn main() -> Result<(), Error> {
    let loopback = Ipv4Addr::new(127, 0, 0, 1);
    let socket = SocketAddrV4::new(loopback, 5555);
    let listener = TcpListener::bind(socket)?;
    let port = listener.local_addr()?;
    println!("Listening on {}, access this port to end the program", port);
    let (tcp_stream, addr) = listener.accept()?; // 阻塞，直到被请求
    println!("Connection received! {:?} is sending data.", addr);

    let mut reader = BufReader::new(tcp_stream);
    let mut line = String::new();
    while reader.read_line(&mut line)? > 0 {
        println!("{:?} says {}", addr, line.trim_end());
        line.clear();
    }
    Ok(())
}
