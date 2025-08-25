use bitflags::bitflags;
use std::fmt;

bitflags! {
  struct MyFlags: u32 {
    const FLAG_A = 0b0000_0001;
    const FLAG_B = 0b0000_0010;
    const FLAG_C = 0b0000_0100;
    const FLAG_ABC = Self::FLAG_A.bits() | Self::FLAG_B.bits() | Self::FLAG_C.bits();
  }
}

impl MyFlags {
    pub fn clear(&mut self) -> &mut MyFlags {
        *self = MyFlags::empty();
        self
    }
}

impl fmt::Display for MyFlags {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "{:032b}", self.bits())
    }
}

pub fn new() {
    let e1 = MyFlags::FLAG_A | MyFlags::FLAG_C;
    let e2 = MyFlags::FLAG_B | MyFlags::FLAG_C;

    let mut flags = MyFlags::FLAG_ABC;

    println!("{:>18} {}", "e1 is:", e1);
    println!("{:>18} {}", "e2 is:", e2);
    println!("{:>18} {}", "the flags is:", flags);

    flags.clear();

    println!("{:>18} {}", "reseted flags is:", flags);
}
