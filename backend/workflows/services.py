def execute_intent(intent, entities):
    actions = {"BOOK_APPOINTMENT":"appointment_booking","RESCHEDULE_APPOINTMENT":"appointment_reschedule",
               "CANCEL_APPOINTMENT":"appointment_cancellation","DOCTOR_AVAILABILITY":"availability_lookup",
               "APPOINTMENT_REMINDER":"reminder_setup"}
    return {"workflow":actions.get(intent,"conversation"),"intent":intent,"entities":entities,"status":"READY"}
