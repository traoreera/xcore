from fastapi import APIRouter
from manager.task.corethread import ServiceManager
from runtimer import core_task_threads,backgroundtask, backgroundtask_manager, crontab

task = APIRouter(
    prefix="/tasks",
    tags=["tasks", "core"],)



@task.get('/resources')
def resources():
    taskList = {}
    for task in backgroundtask_manager.list_services():
        usage = backgroundtask_manager.get_service_resource_usage(task["service"])
        taskList[task["name"]] = usage

    return taskList


@task.post('/stop/{name}')
def start_task(name:str):
    
    if backgroundtask_manager.remove_service(name): return {"success":True}
    else: return {"success":False}


@task.get("/name")
def get_task_name():
    tasks= backgroundtask_manager.list_services()

    return {task['name']:task['status'] for task in tasks}


@task.post('/restart/{name}')
def restart_task(name:str):
    if backgroundtask_manager.restart(name): return {"success":True}
    else: return {"success":False}

@task.post('/add/')
def stop_task(name:str, target:str):
    if backgroundtask_manager.add_service(name, target): return {"success":True}
    else: return {"success":False}


@task.get('/scheduler')
def back_ground_task():

   return  backgroundtask.list_tasks()


@task.post("/scheduler/{name}")
def get_meta_data(name:str):
    
    return backgroundtask.extract_metadata(name)


@task.get('/cron')
def cron():
    return crontab.get_jobs_info()