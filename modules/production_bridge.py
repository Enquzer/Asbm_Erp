from .production_models import ProductionRecord, Machine, ProductionConfig, db
from .models import DutyStation

def get_production_data(period_type='Monthly'):
    # Return production records filtered by period_type
    return ProductionRecord.query.filter_by(period_type=period_type).all()

def get_duty_station_summary(period):
    # Calculate summary of production by duty station
    summary = {}
    records = ProductionRecord.query.filter_by(period_type=period).all()
    for record in records:
        machine = Machine.query.get(record.machine_id)
        if not machine:
            continue
        ds = DutyStation.query.get(machine.duty_station_id)
        if not ds:
            continue
        if ds.name not in summary:
            summary[ds.name] = {'plan': 0, 'actual': 0}
        config = ProductionConfig.query.filter_by(duty_station_id=machine.duty_station_id).first()
        if not config:
            continue
        capacity = machine.manual_capacity or (machine.installed_capacity * machine.efficiency_factor * config.working_hours * config.working_days)
        summary[ds.name]['plan'] += capacity
        summary[ds.name]['actual'] += record.actual_quantity
    return summary

def calculate_plan(machine, period, start_date, end_date):
    if not machine:
        return 0
    config = ProductionConfig.query.filter_by(duty_station_id=machine.duty_station_id).first()
    if not config:
        return 0
    # Simple calculation: use installed capacity adjusted by efficiency and working hours/days
    capacity = machine.manual_capacity or (machine.installed_capacity * machine.efficiency_factor * config.working_hours * config.working_days)
    return capacity