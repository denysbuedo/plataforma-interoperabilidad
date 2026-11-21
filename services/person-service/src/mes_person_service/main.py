from mes_common.app import create_service_app

from mes_person_service.operator import router as operator_router

app = create_service_app(title="MES Person Service", service_name="person-service")
app.include_router(operator_router)
