use unicode_segmentation::UnicodeSegmentation;

pub fn main() {
    let name = "José Guimarães\r\n";
    let graphemes = UnicodeSegmentation::graphemes(name, true)
    	.collect::<Vec<&str>>();
    println!("{:?}", graphemes);
}
