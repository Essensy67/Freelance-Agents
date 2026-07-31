from freelance_agents.core.employees import Employee, EmployeeStatus


async def test_employee_start_and_stop_changes_status() -> None:
    employee = Employee(name="Alex", role="Developer")

    assert employee.status is EmployeeStatus.OFFLINE

    await employee.start()
    assert employee.status is EmployeeStatus.AVAILABLE

    await employee.stop()
    assert employee.status is EmployeeStatus.OFFLINE
