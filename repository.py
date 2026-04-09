import sqlite3
from abc import ABC, abstractmethod
from typing import List
from models import Task


class TaskRepositoryInterface(ABC):
    @abstractmethod
    def get_all(self) -> List[Task]:
        pass

    @abstractmethod
    def save(self, task: Task) -> None:
        pass

    @abstractmethod
    def update(self, task_id: int, done: bool) -> None:
        pass

    @abstractmethod
    def delete(self, task_id: int) -> None:
        pass


class SQLiteTaskRepository(TaskRepositoryInterface):
    def __init__(self, db_file="tasks.db"):
        self.db_file = db_file
        self._create_table()

    def _connect(self) -> sqlite3.Connection:
        try:
            return sqlite3.connect(self.db_file)
        except sqlite3.Error as exc:
            raise ValueError(f"Could not connect to database '{self.db_file}'.") from exc

    def _create_table(self) -> None:
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS tasks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        done INTEGER NOT NULL,
                        deadline TEXT,
                        priority TEXT
                    )
                    """
                )
        except sqlite3.Error as exc:
            raise ValueError("Could not initialize the tasks table.") from exc

    def get_all(self) -> List[Task]:
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT id, title, done, deadline, priority FROM tasks"
                ).fetchall()
        except sqlite3.Error as exc:
            raise ValueError("Could not load tasks from the database.") from exc

        return [
            Task(
                id=row[0],
                title=row[1],
                done=bool(row[2]),
                deadline=row[3],
                priority=row[4],
            )
            for row in rows
        ]

    def save(self, task: Task) -> None:
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO tasks (title, done, deadline, priority) VALUES (?, ?, ?, ?)",
                    (task.title, int(task.done), task.deadline, task.priority),
                )
        except sqlite3.Error as exc:
            raise ValueError("Could not save the task.") from exc

    def update(self, task_id: int, done: bool) -> None:
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    "UPDATE tasks SET done = ? WHERE id = ?",
                    (int(done), task_id),
                )
        except sqlite3.Error as exc:
            raise ValueError("Could not update the task.") from exc

        if cursor.rowcount == 0:
            raise ValueError(f"Task with id {task_id} was not found.")

    def delete(self, task_id: int) -> None:
        try:
            with self._connect() as conn:
                cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        except sqlite3.Error as exc:
            raise ValueError("Could not delete the task.") from exc

        if cursor.rowcount == 0:
            raise ValueError(f"Task with id {task_id} was not found.")
