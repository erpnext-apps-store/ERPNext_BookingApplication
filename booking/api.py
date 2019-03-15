from __future__ import unicode_literals
import frappe
from frappe.utils import flt, cint, cstr, add_days, getdate, get_datetime, get_time, validate_email_add, today, add_years, format_datetime, nowtime

@frappe.whitelist(allow_guest = True)
def TimeToDecimal(time):
  (h, m, s) = str(time).split(':')

  if '.' in str(s):
    s = str(s).split('.')
    result = int(h) * 60 + int(m) + int(s[0])/60
  else:
    result = int(h) * 60 + int(m) + int(s)/60

  return str(flt(result)/60)

@frappe.whitelist(allow_guest = True)
def get_availability_data(booking_date, barber_beautician, service, from_time, to_time, days):
  """
  Get availability data of 'Barber / Beautician' on 'date'
  :param date: Date to check in schedule
  :param barber_beautician: Name of the Barber / Beautician
  :param service: Duration of service
  :return: dict containing a list of available slots, list of appointments and duration of service
  """
  date_list = []
  count = 0
  for i in range(64):
    temp_date = add_days(getdate(booking_date),i)
    weekday = temp_date.strftime("%A")
    if weekday in days:
      date_list.append(temp_date)
      count+=1
    if count == 9:
      break
  
  result_dict = {}
  for selected_date in date_list:
    date = getdate(selected_date)
    # date = getdate(date)
    weekday = date.strftime("%A")

    available_slots = []
    barber_beautician_schedule_name = None
    barber_beautician_schedule = None
    service_durations = None
    branch_holiday_name = None
    barber_beautician_holiday_name = None
    is_holiday = 'No'
    is_on_leave = 'No'
    has_barber_schedule = 'Yes'
    is_barber_available = 'Yes'

    # if branch holiday return
    employee_branch = frappe.db.get_value("Employee", barber_beautician, "branch")
    branch_holiday_name = frappe.db.get_value("Branch", employee_branch, "default_holiday_list")
    if branch_holiday_name:
      branch_holidays = frappe.get_doc("Holiday List", branch_holiday_name)

      if branch_holidays:
        for t in branch_holidays.holidays:
          if t.holiday_date == date:
            is_holiday = 'Yes'

    # if barber holiday return
    barber_beautician_holiday_name = frappe.db.get_value("Employee", barber_beautician, "holiday_list")
    if barber_beautician_holiday_name:
      barber_beautician_holidays = frappe.get_doc("Holiday List", barber_beautician_holiday_name)

      if barber_beautician_holidays:
        for t in barber_beautician_holidays.holidays:
          if t.holiday_date == date:
            is_holiday = 'Yes'

    # if employee on leave return
    leave_application_list = frappe.db.sql("""SELECT * FROM `tabLeave Application` WHERE `tabLeave Application`.status = 'Approved' AND `tabLeave Application`.employee = %s AND (%s BETWEEN `tabLeave Application`.from_date AND `tabLeave Application`.to_date)""" ,(cstr(barber_beautician), cstr(date)),as_dict = 1)

    if leave_application_list and len(leave_application_list) > 0:
      is_on_leave = 'Yes'

    # get barber's schedule
    barber_beautician_schedule_name = frappe.db.get_value("Employee", barber_beautician, "daily_schedule_list")
    if barber_beautician_schedule_name:
      barber_beautician_schedule = frappe.get_doc("Employee Schedule", barber_beautician_schedule_name)
      service_durations = frappe.db.get_value("Item", service, "service_duration")
    else:
      has_barber_schedule = 'No'

    if barber_beautician_schedule:
      for t in barber_beautician_schedule.time_slots:

        from_time_to_decimal = TimeToDecimal(from_time)
        to_time_to_decimal = TimeToDecimal(to_time)
        slot_time_in_decimal =  TimeToDecimal(t.from_time)

        if weekday == t.day:
          if str(date) == str(getdate()):
            current_time_in_decimal = TimeToDecimal(nowtime())

            if flt(slot_time_in_decimal) >= flt(current_time_in_decimal): 
              slots = {"from_time":t.from_time, "is_available":1}
              if flt(slot_time_in_decimal) >= flt(from_time_to_decimal) and flt(slot_time_in_decimal)<= flt(to_time_to_decimal):
                available_slots.append(slots)
            else:
              slots = {"from_time":t.from_time, "is_available":0}
              if flt(slot_time_in_decimal) >= flt(from_time_to_decimal) and flt(slot_time_in_decimal)<= flt(to_time_to_decimal):
                available_slots.append(slots)

          else:
            slots = {"from_time":t.from_time, "is_available":1}
            if flt(slot_time_in_decimal) >= flt(from_time_to_decimal) and flt(slot_time_in_decimal)<= flt(to_time_to_decimal):
              available_slots.append(slots)

    if not service_durations:
      service_durations = 0

    # if employee not available return
    if not available_slots:
      # TODO: return available slots in nearby dates
      is_barber_available = 'No'

    # get appointments on that day for employee
    appointments = frappe.get_all(
      "Event",
      filters=[["barber__beautician", "=", barber_beautician], ["appointment_date","=", date], ["workflow_state", "in", ('Approved','Opened') ]],
      fields=["name", "appointment_time", "duration", "workflow_state"])

    for aptmnt in appointments:
      start_time = TimeToDecimal(aptmnt.appointment_time)
      end_time = flt(TimeToDecimal(aptmnt.appointment_time)) + flt(aptmnt.duration)/60

      for slot in available_slots:
        slot_time = TimeToDecimal(slot['from_time'])
        if (flt(start_time) <= flt(slot_time)) and (flt(end_time) > flt(slot_time)):
          slot['is_available'] = 0
    
    # Code to disable the time slot which don't have enough time to complete the appointment START.
    day_end_time_decimal = TimeToDecimal(get_day_end_time(date, barber_beautician))
          
    for slot in available_slots:
    
      start_time = TimeToDecimal(slot['from_time'])
      end_time = flt(TimeToDecimal(slot['from_time'])) + flt(service_durations)/60
      
      if slot['is_available'] == 1:
      
        for s in available_slots:
        
          slot_time = TimeToDecimal(s['from_time'])
          
          if start_time <= slot_time and end_time > slot_time:
            if s['is_available'] == 0:
              slot['is_available'] = 0
                
      if end_time > day_end_time_decimal:
        slot['is_available'] = 0
    # Code to disable the time slot which don't have enough time to complete the appointment END.     

    result_dict[str(date)] = {
      "day":weekday,
      "available_slots": available_slots,
      # "appointments": appointments,
      "duration_of_service": service_durations,
      "is_holiday": is_holiday,
      "is_on_leave":is_on_leave,
      "has_barber_schedule": has_barber_schedule,
      "is_barber_available": is_barber_available,
      "day_end_time": get_day_end_time(date, barber_beautician)
    }

  # sorting dictionary having the date string as a key
  from datetime import datetime
  ordered_data = sorted(result_dict.items(), key = lambda x:datetime.strptime(x[0], '%Y-%m-%d'), reverse=False)

  return ordered_data

# Get end time of the day for barber.
@frappe.whitelist(allow_guest = True)
def get_day_end_time(date, barber_beautician):
  """
  Get end time of 'Barber / Beautician' on 'date'
  :param date: Date to check in schedule
  :param barber_beautician: Name of the Barber / Beautician
  :return: end time of the given date
  """
  barber_beautician_schedule_name = frappe.db.get_value("Employee", barber_beautician, "daily_schedule_list")
  date = getdate(date)
  weekday = date.strftime("%A")
  
  get_end_time = frappe.db.sql("""SELECT Max(`tabEmployee Schedule Time Slot`.to_time) as day_end_time FROM `tabEmployee Schedule` LEFT JOIN `tabEmployee Schedule Time Slot` ON `tabEmployee Schedule`.name = `tabEmployee Schedule Time Slot`.parent WHERE `tabEmployee Schedule`.name = %s AND `tabEmployee Schedule Time Slot`.day = %s""" ,(cstr(barber_beautician_schedule_name),cstr(weekday)),as_dict = 1)
  if get_end_time and len(get_end_time) > 0:
    return cstr(get_end_time[0]['day_end_time']) or "00:00:00"

@frappe.whitelist()
def employee_name_by_service(service):
  cond = ''
  if service:
    cond = 'and `tabServices`.service = "' + str(service) + '"'

  return frappe.db.sql("""SELECT DISTINCT `tabEmployee`.name, `tabEmployee`.employee_name, `tabServices`.billing_rate FROM `tabEmployee` LEFT JOIN `tabServices` ON `tabServices`.parent = `tabEmployee`.name
    WHERE `tabEmployee`.status = 'Active' AND `tabServices`.is_provided = 'Yes' AND `tabEmployee`.is_service_provider = 1
       {cond} 
    ORDER BY
      `tabEmployee`.name ASC""".format(
      cond=cond))

@frappe.whitelist()
def system_currency():

  system_currency = {}

  default_currency = frappe.db.get_value("Global Defaults", None, "default_currency")
  
  system_currency["currency"] = default_currency
  system_currency["symbol"] = frappe.db.get_value("Currency", default_currency, "symbol")

  return system_currency