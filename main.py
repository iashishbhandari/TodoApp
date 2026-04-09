from datetime import datetime
from repository import SQLiteTaskRepository
from services import TaskService


def create_service():
    return TaskService(SQLiteTaskRepository("tasks.db"))


def validate_non_empty_title(title):
    normalized_title = title.strip()
    if not normalized_title:
        raise ValueError("Title cannot be empty.")
    return normalized_title


def validate_deadline(deadline):
    normalized_deadline = deadline.strip()
    try:
        datetime.strptime(normalized_deadline, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("Invalid date format. Use YYYY-MM-DD.") from exc
    return normalized_deadline


def validate_priority(priority):
    normalized_priority = priority.strip().capitalize()
    if normalized_priority not in {"Low", "Medium", "High"}:
        raise ValueError("Invalid priority. Choose Low, Medium, or High.")
    return normalized_priority


def prompt_task_details():
    title = validate_non_empty_title(input("Enter task: "))
    deadline = validate_deadline(input("Enter deadline (YYYY-MM-DD): "))
    priority = validate_priority(input("Enter priority (Low/Medium/High): "))
    return title, deadline, priority


def render_tasks(tasks):
    if not tasks:
        print("No tasks.")
        return

    today = datetime.today().date()
    for index, task in enumerate(tasks, start=1):
        status = "✔" if task.done else "✘"
        try:
            deadline_date = datetime.strptime(task.deadline, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(
                f"Task '{task.title}' has an invalid deadline: {task.deadline}."
            ) from exc
        warning = " | ⚠ OVERDUE" if deadline_date < today and not task.done else ""
        print(f"{index}. {task.title} [{status}]")
        print(f"   📅 {task.deadline} | 🔥 {task.priority}{warning}")


def choose_task_id(tasks):
    if not tasks:
        raise ValueError("There are no tasks to choose from.")

    try:
        choice = int(input("Task number: ").strip()) - 1
    except ValueError as exc:
        raise ValueError("Task number must be a valid integer.") from exc

    if choice < 0 or choice >= len(tasks):
        raise ValueError("Invalid task number.")
    return tasks[choice].id


def validate_menu_choice(choice):
    normalized_choice = choice.strip()
    if normalized_choice not in {"1", "2", "3", "4", "5"}:
        raise ValueError("Invalid option. Choose 1 to 5.")
    return normalized_choice


def main():
    service = create_service()

    while True:
        print("\n1.Add 2.View 3.Done 4.Delete 5.Exit")
        choice = input("Choose: ")

        try:
            choice = validate_menu_choice(choice)

            if choice == "1":
                title, deadline, priority = prompt_task_details()
                service.add_task(title, deadline, priority)
                print("✅ Task added successfully!")
            elif choice == "2":
                render_tasks(service.list_tasks())
            elif choice == "3":
                tasks = service.list_tasks()
                render_tasks(tasks)
                service.mark_done(choose_task_id(tasks))
                print("✅ Task marked as done.")
            elif choice == "4":
                tasks = service.list_tasks()
                render_tasks(tasks)
                service.delete_task(choose_task_id(tasks))
                print("🗑️ Task deleted.")
            elif choice == "5":
                break
        except ValueError as exc:
            print("❌", exc)


if __name__ == "__main__":
    main()
