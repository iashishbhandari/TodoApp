from datetime import datetime
from typing import List
from models import Task
from repository import TaskRepositoryInterface


class TaskService:
    VALID_PRIORITIES = ("Low", "Medium", "High")

    def __init__(self, repo: TaskRepositoryInterface):
        self.repo = repo

    def add_task(self, title: str, deadline: str, priority: str) -> Task:
        normalized_title = title.strip()
        normalized_deadline = deadline.strip()
        normalized_priority = priority.strip().capitalize()

        if not normalized_title:
            raise ValueError("Title cannot be empty.")

        try:
            datetime.strptime(normalized_deadline, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("Invalid date format. Use YYYY-MM-DD.") from exc

        if normalized_priority not in self.VALID_PRIORITIES:
            raise ValueError("Invalid priority. Choose Low, Medium, or High.")

        task = Task(
            title=normalized_title,
            done=False,
            deadline=normalized_deadline,
            priority=normalized_priority,
        )
        self.repo.save(task)
        return task

    def list_tasks(self) -> List[Task]:
        tasks = self.repo.get_all()
        priority_order = {"High": 1, "Medium": 2, "Low": 3}
        return sorted(
            tasks,
            key=lambda task: (
                priority_order.get(task.priority, 4),
                0 if not task.done else 1,
                task.deadline,
                task.title.lower(),
            ),
        )

    def mark_done(self, task_id: int) -> None:
        self.repo.update(task_id, True)

    def delete_task(self, task_id: int) -> None:
        self.repo.delete(task_id)
