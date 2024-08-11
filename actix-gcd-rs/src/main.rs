use actix_web::{web, App, HttpResponse, HttpServer, Responder};
fn main() {
    let server = HttpServer::new(|| App::new().route("/", web::get().to(get_index)));
    println!("Server running at http://localhost:8080");
    server
        .bind("127.0.0.1:8080")
        .expect("Can not bind to port 8080")
        .run()
}

fn get_index() -> impl Responder {
    HttpResponse::Ok().body("Hello world!")
}
