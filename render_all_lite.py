import glob
import json
import os
import shutil
import traceback
import time

import yaml
from jinja2 import Environment, FileSystemLoader, TemplateError
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


def load_data():
    """Load all JSON and YAML files from the data/ directory and return a single dictionary.

    Note that if a key is repeated in multiple files, the last file loaded will take precedence.
    """
    data = {}

    # Load JSON files, handling .json and .JSON file extensions.
    for json_file in glob.glob("data/*.[jJ][sS][oO][nN]"):
        try:
            with open(json_file, "r") as f:
                data.update(json.load(f))
            print(f"Loaded data from {json_file}")
        except Exception as e:
            print(f"Error loading data from {json_file}: {e}")
            traceback.print_exc()

    # Load YAML files, handling .yaml and .YAML extensions.
    for yaml_file in glob.glob("data/*.[yY][aA][mM][lL]"):
        try:
            with open(yaml_file, "r") as f:
                data.update(yaml.safe_load(f))
            print(f"Loaded data from {yaml_file}")
        except Exception as e:
            print(f"Error loading data from {yaml_file}: {e}")
            traceback.print_exc()

    return data


def copy_html_files():
    """Copy .html files from templates/ to site/ without parsing them."""

    # Ensure the output path exists
    if not os.path.exists("site"):
        os.makedirs("site")

    # Walk the templates directory and copy all .html files
    # Much of what's here is to fudge around path inconsistencies between
    # Windows and Unix-like systems
    for html_file in glob.glob("templates/**/*.html", recursive=True):
        try:
            destination = os.path.join("site", os.path.relpath(html_file, "templates"))
            outdir = os.path.dirname(destination)
            # Ensure the output directory exists (mirror directory structure within templates/)
            if not os.path.exists(outdir):
                os.makedirs(outdir)
            # Remove the destination file if it already exists
            if os.path.exists(destination):
                os.remove(destination)
            # Copy the file
            shutil.copy(html_file, destination)
            print(f"Copied {html_file} to {destination}")
        except Exception as e:
            print(f"Error copying {html_file} to {destination}: {e}")
            traceback.print_exc()


def copy_img_files():
    """Copy the entire templates/img/ directory to site/img/."""

    src_dir = "templates/img"
    dest_dir = "site/img"

    # Ensure the output path exists
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    shutil.copytree(src_dir, dest_dir)
    print(f"Copied {src_dir} to {dest_dir}")


def render_all_templates(env, data, trigger_file=None):
    """Render all templates, excluding partials."""

    # If a trigger file is provided, note which one caused the rebuild.
    # We're going to rebuild everything anyway, but this is useful context for the user.
    if trigger_file:
        print(f">>> Rebuild triggered by change in: {trigger_file}")

    # Ensure the output path exists
    if not os.path.exists("site"):
        os.makedirs("site")

    # Collect templates from templates/ directory, excluding partials
    # Template files are assumed to end in .j2 or .jinja extensions.
    template_files = [
        f
        for f in glob.glob(os.path.join("templates", "**", "*.*"), recursive=True)
        if f.endswith((".j2", ".jinja")) and "partials" not in f
    ]

    # Make sure we include copying across .html files in our rebuild.
    copy_html_files()

    # Render each template
    # Much of this is fudging around path inconsistencies between Windows and Unix-like systems
    for template_path in template_files:
        try:
            template_rel_path = os.path.relpath(template_path, "templates").replace(os.sep, "/")
            template = env.get_template(template_rel_path)
            output = template.render(data)
            # Compute the output path, including renaming .j2 and .jinja files to .html
            outname = os.path.join(
                "site",
                os.path.normpath(template_rel_path)
                .replace(".html.j2", ".html")
                .replace(".j2", ".html")
                .replace(".html.jinja", ".html")
                .replace(".jinja", ".html"),
            )
            # Ensure the output directory exists
            outdir = os.path.dirname(outname)
            if not os.path.exists(outdir):
                os.makedirs(outdir)
            # Now actually write the output
            with open(outname, "w") as out:
                out.write(output)
            print(f"Rendered {template_path} to {outname}")
        except TemplateError as e:
            print(f"Error rendering {template_path}: {e}")
            traceback.print_exc()
        except Exception as e:
            print(f"Unexpected error rendering {template_path}: {e}")
            traceback.print_exc()


def render_all(trigger_file=None):
    """Handle file update events and trigger a rebuild of all templates."""
    # In some circumstances the trigger_file is passed as a list, so we need to handle that.
    if isinstance(trigger_file, list):
        trigger_file = trigger_file[0]
    # Normalize the path to avoid issues with Windows paths, but allow for their being no
    # file reference which has triggered the rebuild (on first run, for example)
    trigger_file = os.path.normpath(trigger_file) if trigger_file else None
    # Set up the Jinja2 environment and call render_all_templates to do the work
    env = Environment(loader=FileSystemLoader("templates"))
    data = load_data()
    render_all_templates(env, data, trigger_file)
    copy_img_files()


class ChangeHandler(FileSystemEventHandler):
    """Handle file system events and trigger a rebuild of all templates if necessary."""
    def __init__(self):
        super().__init__()
        self.last_event_time = 0
        self.last_event_path = None
        self.debounce_delay = 5  # seconds

    def should_process_event(self, event_path):
        """Keeps track of what's caused a render, and tries to avoid duplicate renders.

        This is a simple debounce mechanism to avoid multiple renders for a single change event.
        I'm not completely convinced it works, but 'it's better than it was'.
        """
        current_time = time.time()
        if (self.last_event_path != event_path) or (current_time - self.last_event_time > self.debounce_delay):
            self.last_event_time = current_time
            self.last_event_path = event_path
            return True
        return False

    def on_modified(self, event):
        """Handle a file modification event."""
        if self.should_process_event(event.src_path):
            rel_path = os.path.normpath(os.path.relpath(event.src_path))
            if rel_path.startswith(os.path.normpath("templates" + os.sep)) or rel_path.startswith(os.path.normpath("data" + os.sep)):
                render_all(event.src_path)

    def on_created(self, event):
        """Handle a file creation event."""
        if self.should_process_event(event.src_path):
            rel_path = os.path.normpath(os.path.relpath(event.src_path))
            if rel_path.startswith(os.path.normpath("templates" + os.sep)) or rel_path.startswith(os.path.normpath("data" + os.sep)):
                render_all(event.src_path)

    def on_deleted(self, event):
        """Handle a file deletion event."""
        if self.should_process_event(event.src_path):
            rel_path = os.path.normpath(os.path.relpath(event.src_path))
            if rel_path.startswith(os.path.normpath("templates" + os.sep)) or rel_path.startswith(os.path.normpath("data" + os.sep)):
                render_all(event.src_path)


if __name__ == "__main__":
    # Initial render on startup
    render_all()

    # Set up the file system event handler and observer
    event_handler = ChangeHandler()
    observer = Observer()
    # Monitor the templates and data directories for changes, recursively
    observer.schedule(event_handler, "templates/", recursive=True)
    observer.schedule(event_handler, "data/", recursive=True)
    observer.start()

    try:
        while True:
            pass
    except KeyboardInterrupt:
        # Clean up on exit
        observer.stop()
    observer.join()
