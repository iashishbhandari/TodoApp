import os
import tempfile
import unittest
from datetime import date, timedelta

from app import create_app
from main import (
    validate_deadline,
    validate_menu_choice,
    validate_non_empty_title,
    validate_priority,
)
from models import Task
from repository import SQLiteTaskRepository
from services import TaskService


class FakeRepo:
    def __init__(self):
        self.tasks = []
        self.next_id = 1

    def get_all(self):
        return list(self.tasks)

    def save(self, task):
        stored_task = Task(
            id=self.next_id,
            title=task.title,
            done=task.done,
            deadline=task.deadline,
            priority=task.priority,
        )
        self.next_id += 1
        self.tasks.append(stored_task)

    def update(self, task_id, done):
        for task in self.tasks:
            if task.id == task_id:
                task.done = done
                return
        raise ValueError(f"Task with id {task_id} was not found.")

    def delete(self, task_id):
        for index, task in enumerate(self.tasks):
            if task.id == task_id:
                self.tasks.pop(index)
                return
        raise ValueError(f"Task with id {task_id} was not found.")


class TestTaskService(unittest.TestCase):
    def setUp(self):
        self.repo = FakeRepo()
        self.service = TaskService(self.repo)

    def test_add_task(self):
        task = self.service.add_task("Test", "2026-04-10", "High")

        self.assertEqual(task.title, "Test")
        self.assertEqual(len(self.repo.tasks), 1)
        self.assertEqual(self.repo.tasks[0].priority, "High")

    def test_invalid_title(self):
        with self.assertRaises(ValueError):
            self.service.add_task("", "2026-04-10", "High")

    def test_invalid_deadline(self):
        with self.assertRaises(ValueError):
            self.service.add_task("Test", "10-04-2026", "High")

    def test_invalid_priority(self):
        with self.assertRaises(ValueError):
            self.service.add_task("Test", "2026-04-10", "Urgent")

    def test_mark_done(self):
        self.service.add_task("Test", "2026-04-10", "High")

        self.service.mark_done(1)

        self.assertTrue(self.repo.tasks[0].done)

    def test_delete_task(self):
        self.service.add_task("Test", "2026-04-10", "High")

        self.service.delete_task(1)

        self.assertEqual(self.repo.tasks, [])

    def test_list_tasks_sorts_by_priority(self):
        self.service.add_task("Low task", "2026-04-12", "Low")
        self.service.add_task("High task", "2026-04-11", "High")
        self.service.add_task("Medium task", "2026-04-10", "Medium")

        tasks = self.service.list_tasks()

        self.assertEqual([task.priority for task in tasks], ["High", "Medium", "Low"])

    def test_list_tasks_prioritizes_pending_before_done_within_same_priority(self):
        self.service.add_task("Done task", "2026-04-10", "High")
        self.service.add_task("Pending task", "2026-04-11", "High")
        self.service.mark_done(1)

        tasks = self.service.list_tasks()

        self.assertEqual([task.title for task in tasks], ["Pending task", "Done task"])


class TestCliValidation(unittest.TestCase):
    def test_validate_non_empty_title(self):
        self.assertEqual(validate_non_empty_title("  Test  "), "Test")

    def test_validate_non_empty_title_raises(self):
        with self.assertRaises(ValueError):
            validate_non_empty_title("   ")

    def test_validate_deadline_raises(self):
        with self.assertRaises(ValueError):
            validate_deadline("2026/04/10")

    def test_validate_priority_raises(self):
        with self.assertRaises(ValueError):
            validate_priority("urgent")

    def test_validate_menu_choice_raises(self):
        with self.assertRaises(ValueError):
            validate_menu_choice("9")


class TestSQLiteTaskRepository(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_tasks.db")
        self.repo = SQLiteTaskRepository(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_get_all_returns_empty_list_initially(self):
        self.assertEqual(self.repo.get_all(), [])

    def test_save_and_get_all(self):
        self.repo.save(Task(title="Write tests", deadline="2026-04-10", priority="High"))

        tasks = self.repo.get_all()

        self.assertEqual(len(tasks), 1)
        self.assertIsNotNone(tasks[0].id)
        self.assertEqual(tasks[0].title, "Write tests")
        self.assertFalse(tasks[0].done)
        self.assertEqual(tasks[0].deadline, "2026-04-10")
        self.assertEqual(tasks[0].priority, "High")

    def test_update_marks_task_done(self):
        self.repo.save(Task(title="Finish report", deadline="2026-04-11", priority="Medium"))
        task_id = self.repo.get_all()[0].id

        self.repo.update(task_id, True)

        tasks = self.repo.get_all()
        self.assertTrue(tasks[0].done)

    def test_update_missing_task_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.repo.update(9999, True)

    def test_delete_removes_task(self):
        self.repo.save(Task(title="Clean inbox", deadline="2026-04-12", priority="Low"))
        task_id = self.repo.get_all()[0].id

        self.repo.delete(task_id)

        self.assertEqual(self.repo.get_all(), [])

    def test_delete_missing_task_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.repo.delete(9999)


class TestWebApp(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "web_tasks.db")
        self.repo = SQLiteTaskRepository(self.db_path)
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE": self.db_path,
                "SECRET_KEY": "test-secret",
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_home_page_loads_successfully(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"TodoApp", response.data)

    def test_posting_valid_task_creates_it_and_redirects(self):
        response = self.client.post(
            "/tasks",
            data={
                "title": "Ship release",
                "deadline": "2026-04-10",
                "priority": "High",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/")

        tasks = self.repo.get_all()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].title, "Ship release")

    def test_posting_invalid_title_returns_error_message(self):
        response = self.client.post(
            "/tasks",
            data={
                "title": "   ",
                "deadline": "2026-04-10",
                "priority": "High",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Title cannot be empty.", response.data)

    def test_posting_invalid_deadline_returns_error_message(self):
        response = self.client.post(
            "/tasks",
            data={
                "title": "Ship release",
                "deadline": "04-10-2026",
                "priority": "High",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Invalid date format. Use YYYY-MM-DD.", response.data)

    def test_posting_invalid_priority_returns_error_message(self):
        response = self.client.post(
            "/tasks",
            data={
                "title": "Ship release",
                "deadline": "2026-04-10",
                "priority": "Urgent",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Invalid priority. Choose Low, Medium, or High.", response.data)

    def test_marking_task_done_updates_it_in_sqlite(self):
        self.repo.save(Task(title="Review PR", deadline="2026-04-10", priority="High"))
        task_id = self.repo.get_all()[0].id

        response = self.client.post(f"/tasks/{task_id}/done", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.repo.get_all()[0].done)

    def test_deleting_task_removes_it_from_sqlite(self):
        self.repo.save(Task(title="Review PR", deadline="2026-04-10", priority="High"))
        task_id = self.repo.get_all()[0].id

        response = self.client.post(f"/tasks/{task_id}/delete", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.repo.get_all(), [])

    def test_list_page_renders_tasks_in_service_sort_order(self):
        self.repo.save(Task(title="Low item", deadline="2026-04-11", priority="Low"))
        self.repo.save(Task(title="Done high", deadline="2026-04-10", priority="High", done=True))
        self.repo.save(Task(title="Pending high", deadline="2026-04-12", priority="High"))

        response = self.client.get("/")
        page = response.get_data(as_text=True)

        self.assertLess(page.index("Pending high"), page.index("Done high"))
        self.assertLess(page.index("Done high"), page.index("Low item"))

    def test_overdue_pending_tasks_are_visibly_marked(self):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        self.repo.save(Task(title="Past due", deadline=yesterday, priority="Medium"))

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"OVERDUE", response.data)


if __name__ == "__main__":
    unittest.main()
