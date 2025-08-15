use ansi_term::{Colour, Style};
fn main() {
    use_color();
    sue_style();
}

fn use_color() {
    println!(
        "This is {} in color, {} in color and {} in color",
        Colour::Red.paint("red"),
        Colour::Blue.paint("blur"),
        Colour::Green.paint("green")
    )
}

fn sue_style() {
    println!(
        "{} and this is not",
        Style::new().bold().paint("This is Bold")
    );

    println!(
        "{}, {} and {}",
        Colour::Yellow.paint("This is colored"),
        Style::new().bold().paint("this is bold"),
        Colour::Yellow.bold().paint("this is bold and colored")
    )
}
