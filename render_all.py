from livereload import Server

from render_all_lite import render_all

if __name__ == "__main__":
    # Initial render on startup
    render_all()

    # Set up the livereload server
    server = Server()

    # Watch for changes in the templates/, data/, and img/ directories.
    # The *args bit here avoids some nasty errors when the watch triggers
    # on a directory create/delete event.
    server.watch("templates/**/*.j2", lambda path, *args: render_all(path))
    server.watch("templates/**/*.jinja", lambda path, *args: render_all(path))
    server.watch("templates/**/*.html", lambda path, *args: render_all(path))
    server.watch("data/*.json", lambda path, *args: render_all(path))
    server.watch("data/*.[yY][aA][mM][lL]", lambda path, *args: render_all(path))
    server.watch("img/**/*.*", lambda path, *args: render_all(path))

    # Serve the site/ directory at http://127.0.0.1:5500
    server.serve(root="site")
