use iced::alignment::Horizontal;
use iced::widget::{Container, button, column, text};
use iced::{Alignment, Element, Length};

pub fn main() -> iced::Result {
    iced::run("A cool counter", Counter::update, Counter::view)
}

#[derive(Default)]
struct Counter {
    value: i64,
}

#[derive(Debug, Clone, Copy)]
enum Message {
    Increment,
    Decrement,
}

impl Counter {
    fn update(&mut self, message: Message) {
        match message {
            Message::Increment => {
                self.value += 1;
            }
            Message::Decrement => {
                self.value -= 1;
            }
        }
    }

    fn view(&self) -> Element<'_, Message> {
        // helper to create same-size buttons
        let make_btn = |label: &'static str, msg: Message| {
            button(
                text(label)
                    .size(20)
                    .width(Length::Fill)
                    .align_x(Horizontal::Center),
            )
            .width(Length::Fixed(80.0))
            .height(Length::Fixed(40.0))
            .on_press(msg)
        };

        let content = column![
            make_btn("+", Message::Increment),
            text(self.value.to_string()).size(40),
            make_btn("-", Message::Decrement),
        ]
        .spacing(16)
        .align_x(Alignment::Center);

        Container::new(content)
            .width(Length::Fill)
            .height(Length::Fill)
            .center(Length::Fill)
            .into()
    }
}
