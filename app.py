from datetime import datetime

from flask import Flask, flash, redirect, render_template, request, url_for

from repository import SQLiteTaskRepository
from services import TaskService


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="todoapp-dev",
        DATABASE="tasks.db",
        TESTING=False,
    )

    if test_config:
        app.config.update(test_config)

    def get_service():
        return TaskService(SQLiteTaskRepository(app.config["DATABASE"]))

    def build_task_view_models(tasks):
        today = datetime.today().date()
        view_models = []

        for task in tasks:
            deadline_date = datetime.strptime(task.deadline, "%Y-%m-%d").date()
            view_models.append(
                {
                    "task": task,
                    "is_overdue": deadline_date < today and not task.done,
                }
            )

        return view_models

    def render_index(status_code=200):
        tasks = get_service().list_tasks()
        return (
            render_template("index.html", task_rows=build_task_view_models(tasks)),
            status_code,
        )

    @app.get("/")
    def index():
        return render_index()

    @app.post("/tasks")
    def create_task():
        service = get_service()

        try:
            service.add_task(
                request.form.get("title", ""),
                request.form.get("deadline", ""),
                request.form.get("priority", ""),
            )
        except ValueError as exc:
            flash(str(exc), "error")
            return render_index(status_code=400)

        flash("Task added successfully!", "success")
        return redirect(url_for("index"))

    @app.post("/tasks/<int:task_id>/done")
    def mark_done(task_id):
        service = get_service()

        try:
            service.mark_done(task_id)
        except ValueError as exc:
            flash(str(exc), "error")
            return render_index(status_code=400)

        flash("Task marked as done.", "success")
        return redirect(url_for("index"))

    @app.post("/tasks/<int:task_id>/delete")
    def delete_task(task_id):
        service = get_service()

        try:
            service.delete_task(task_id)
        except ValueError as exc:
            flash(str(exc), "error")
            return render_index(status_code=400)

        flash("Task deleted.", "success")
        return redirect(url_for("index"))

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
