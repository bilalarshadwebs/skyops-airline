from datetime import datetime, timedelta, time

MIN_CONNECT = 45


class Record:
    """Base class: gives every object an ID, a status and a history."""
    counter = 0

    def __init__(self):
        Record.counter += 1
        self.id = Record.counter
        self.status = "active"
        self.history = []
        self.note("created")

    def note(self, text):
        self.history.append(text)

    def set_status(self, status):
        self.note(f"{self.status} -> {status}")
        self.status = status

    def __repr__(self):
        return f"{type(self).__name__}#{self.id}"


class Qualification(Record):
    """Crew qualification for one aircraft type. Revoking keeps the history."""
    def __init__(self, aircraft_code, expiry):
        super().__init__()
        self.aircraft_code = aircraft_code
        self.expiry = expiry
        self.revoked_on = None

    def valid_on(self, date):
        if self.revoked_on is not None and date >= self.revoked_on:
            return False
        return date < self.expiry

    def revoke(self, date):
        self.revoked_on = date
        self.set_status("revoked")


class RoleAssignment(Record):
    """A role held by an employee between a start and an end date."""
    def __init__(self, role, start):
        super().__init__()
        self.role = role
        self.start = start
        self.end = None


class Person(Record):
    def __init__(self, name):
        super().__init__()
        self.name = name

    def __repr__(self):
        return self.name


class Employee(Person):
    """Any airline employee. Keeps qualifications and a role history."""
    def __init__(self, name, role):
        super().__init__(name)
        self.qualifications = []
        self.roles = [RoleAssignment(role, datetime(2020, 1, 1))]

    def add_qualification(self, qualification):
        self.qualifications.append(qualification)
        self.note(f"qualified {qualification.aircraft_code}")

    def qualified_for(self, code, date):
        for q in self.qualifications:
            if q.aircraft_code == code and q.valid_on(date):
                return True
        return False

    def add_role(self, role, start):
        self.roles.append(RoleAssignment(role, start))

    def end_role(self, role, end):
        for r in self.roles:
            if r.role == role and r.end is None:
                r.end = end
                r.set_status("ended")

    def roles_on(self, date):
        result = []
        for r in self.roles:
            if r.start <= date and (r.end is None or date < r.end):
                result.append(r.role)
        return result


class FlightCrew(Employee):
    """Employees who fly, so their duty hours are limited."""
    MAX_DUTY = 600

    def __init__(self, name, role):
        super().__init__(name, role)
        self.duty_minutes = 0

    def log_duty(self, minutes):
        self.duty_minutes += minutes

    def duty_left(self):
        return self.MAX_DUTY - self.duty_minutes


class Pilot(FlightCrew):
    def promote(self, new_role, date):
        current_roles = self.roles_on(date)
        if current_roles:
            self.end_role(current_roles[0], date)
        self.add_role(new_role, date)


class CabinCrew(FlightCrew):
    def make_senior(self, date):
        """Cabin crew can hold the senior role at the same time as their normal role."""
        self.add_role("Senior Cabin Crew", date)


class EngineeringStaff(Employee):
    def sign_off(self, defect):
        defect.rectify()
        defect.note(f"signed off by {self.name}")


class GroundStaff(Employee):
    def check_in_passenger(self, reservation):
        reservation.check_in()
        reservation.note(f"checked in by {self.name}")

    def handle_bag(self, bag):
        bag.load()


class TravelDocument(Record):
    def __init__(self, number, expiry):
        super().__init__()
        self.number = number
        self.expiry = expiry

    def valid_on(self, date):
        return self.status == "active" and self.expiry > date

    def flag(self):
        self.set_status("flagged")


class Passenger(Person):
    def __init__(self, name):
        super().__init__(name)
        self.documents = []

    def add_document(self, document):
        self.documents.append(document)

    def has_valid_document(self, date):
        for d in self.documents:
            if d.valid_on(date):
                return True
        return False


class AircraftType(Record):
    def __init__(self, code, name):
        super().__init__()
        self.code = code
        self.name = name


class CabinConfiguration(Record):
    """Seat layout of an aircraft."""
    def __init__(self, name, seats):
        super().__init__()
        self.name = name
        self.seats = seats

    def has_seat(self, seat):
        return seat in self.seats

    def capacity(self):
        return len(self.seats)


class MaintenanceItem(Record):
    """Maintenance record. kind is "defect", "inspection" or "work"."""
    def __init__(self, aircraft, description, kind, grounding=True, due=None):
        super().__init__()
        self.aircraft = aircraft
        self.description = description
        self.kind = kind
        self.grounding = grounding
        self.due = due
        if kind == "defect":
            self.set_status("open")
            aircraft.defects.append(self)

    def rectify(self):
        self.set_status("rectified")

    def defer(self):
        """Replace this defect with a deferred one that does not ground the aircraft."""
        deferred = MaintenanceItem(self.aircraft, self.description, "defect", grounding=False)
        deferred.set_status("deferred")
        self.set_status("transformed")
        return deferred

    def record(self, passed, finding=""):
        """Record an inspection result. A failure creates a new defect."""
        if passed:
            self.set_status("passed")
            return None
        self.set_status("failed")
        return MaintenanceItem(self.aircraft, finding, "defect")

    def complete(self):
        self.set_status("done")


class Aircraft(Record):
    def __init__(self, reg, aircraft_type, config, cargo_capacity):
        super().__init__()
        self.reg = reg
        self.type = aircraft_type
        self.config = config
        self.config_history = [config.name]
        self.cargo_capacity = cargo_capacity
        self.defects = []
        self.work = []

    def reconfigure(self, config):
        self.config = config
        self.config_history.append(config.name)
        self.note(f"reconfigured to {config.name}")

    def retire(self):
        self.set_status("retired")

    def ground(self):
        self.set_status("grounded")

    def return_to_service(self):
        self.set_status("active")

    def serviceable(self):
        if self.status != "active":
            return False
        for d in self.defects:
            if d.grounding and d.status == "open":
                return False
        return True

    def report_defect(self, description):
        return MaintenanceItem(self, description, "defect")

    def inspect(self, description):
        return MaintenanceItem(self, description, "inspection")

    def schedule_work(self, description, due):
        work = MaintenanceItem(self, description, "work", due=due)
        self.work.append(work)
        return work

    def work_due_before(self, date):
        result = []
        for w in self.work:
            if w.status == "active" and w.due < date:
                result.append(w)
        return result


class AirportRestriction(Record):
    """Restriction at an airport, such as fog. It is kept after it is lifted."""
    def __init__(self, airport, reason, start):
        super().__init__()
        self.airport = airport
        self.reason = reason
        self.start = start
        self.end = None

    def lift(self, end):
        self.end = end
        self.set_status("lifted")

    def in_force(self, date):
        return self.start <= date and (self.end is None or date < self.end)


class Airport(Record):
    def __init__(self, code, name):
        super().__init__()
        self.code = code
        self.name = name
        self.restrictions = []

    def add_restriction(self, restriction):
        self.restrictions.append(restriction)

    def restrictions_at(self, date):
        result = []
        for r in self.restrictions:
            if r.in_force(date):
                result.append(r)
        return result

    def __repr__(self):
        return self.code


class Route(Record):
    def __init__(self, origin, dest, minutes):
        super().__init__()
        self.origin = origin
        self.dest = dest
        self.minutes = minutes


class ScheduledService(Record):
    """A timetable entry. Each day it is flown, it becomes a Flight."""
    def __init__(self, number, route, dep_time):
        super().__init__()
        self.number = number
        self.route = route
        self.dep_time = dep_time

    def fly_on(self, day, aircraft, international=False):
        departure = datetime.combine(day, self.dep_time)
        return Flight(self.number, self.route, departure, aircraft, international, self)


class CrewAssignment(Record):
    def __init__(self, flight, member):
        super().__init__()
        self.flight = flight
        self.member = member
        self.role_at_time = member.roles_on(flight.departure)

    def release(self):
        self.set_status("released")


class CheckIn(Record):
    def __init__(self, reservation):
        super().__init__()
        self.reservation = reservation

    def withdraw(self):
        self.set_status("withdrawn")


class SpecialRequest(Record):
    """Special service request, such as mobility assistance."""
    def __init__(self, reservation, kind):
        super().__init__()
        self.reservation = reservation
        self.kind = kind

    def fulfil(self):
        self.set_status("fulfilled")


class Reservation(Record):
    """A passenger's booking on a flight."""
    LIVE = ["active", "checked_in", "boarded"]

    def __init__(self, passenger, flight, seat=None, connection_at=None):
        super().__init__()
        self.passenger = passenger
        self.flight = flight
        self.seat = None
        self.booked_config = flight.aircraft.config.name
        self.connection_at = connection_at
        self.checkin = None
        self.requests = []
        if seat:
            self.assign_seat(seat)

    def is_live(self):
        return self.status in self.LIVE

    def assign_seat(self, seat):
        if not self.flight.aircraft.config.has_seat(seat):
            raise ValueError(f"seat {seat} not on {self.flight.aircraft.config.name}")
        for r in self.flight.reservations:
            if r is not self and r.seat == seat and r.is_live():
                raise ValueError(f"seat {seat} taken")
        self.seat = seat
        self.note(f"seat {seat}")

    def add_request(self, kind):
        request = SpecialRequest(self, kind)
        self.requests.append(request)
        return request

    def check_in(self):
        if self.flight.international and not self.passenger.has_valid_document(self.flight.departure):
            raise ValueError("travel document invalid")
        if not self.seat:
            raise ValueError("no seat")
        self.checkin = CheckIn(self)
        self.set_status("checked_in")

    def board(self):
        if self.status != "checked_in":
            raise ValueError("not checked in")
        self.set_status("boarded")

    def remove_from_flight(self):
        if self.checkin:
            self.checkin.withdraw()
        for bag in self.flight.baggage:
            if bag.owner is self and bag.status in ["active", "loaded"]:
                bag.offload()
        self.note(f"released seat {self.seat}")
        self.seat = None
        self.set_status("removed")

    def rebook(self, new_flight, seat=None):
        new_reservation = new_flight.book(self.passenger, seat)
        self.set_status("rebooked")
        self.note(f"moved to {new_flight.number}")
        return new_reservation

    def __repr__(self):
        return f"{self.passenger.name}({self.status},{self.seat})"


class Baggage(Record):
    """Checked bag. Its routing can differ from its owner's flight."""
    def __init__(self, tag, owner, weight):
        super().__init__()
        self.tag = tag
        self.owner = owner
        self.weight = weight
        self.routing = [owner.flight]

    def route_via(self, flight):
        self.routing.append(flight)
        self.note(f"routed via {flight.number}")

    def routing_mismatch(self):
        return self.routing[-1] is not self.owner.flight

    def load(self):
        self.set_status("loaded")

    def offload(self):
        self.set_status("offloaded")

    def damaged(self, damage):
        claim = DamagedBaggage(self.tag, self.owner, self.weight, damage)
        claim.routing = self.routing
        self.owner.flight.baggage.append(claim)
        self.set_status("transformed")
        return claim


class DamagedBaggage(Baggage):
    """A bag with an open damage claim."""
    def __init__(self, tag, owner, weight, damage):
        super().__init__(tag, owner, weight)
        self.damage = damage
        self.set_status("claim_open")

    def settle(self):
        self.set_status("claim_settled")


class Cargo(Record):
    """Ordinary cargo shipment."""
    def __init__(self, awb, weight, description, flight):
        super().__init__()
        self.awb = awb
        self.weight = weight
        self.description = description
        self.flight = flight
        flight.cargo.append(self)
        self.set_status("accepted")

    def can_load(self):
        return True

    def load(self):
        if not self.can_load():
            raise ValueError(f"{self.awb} cannot be loaded")
        self.set_status("loaded")

    def deliver(self):
        self.set_status("delivered")

    def as_dangerous(self, un_class):
        """Cargo accepted as ordinary, later found to be dangerous goods."""
        dangerous = DangerousCargo(self.awb, self.weight, self.description, self.flight, un_class)
        self.set_status("transformed")
        return dangerous


class SpecialCargo(Cargo):
    """Cargo that needs paperwork before it can be loaded."""
    def __init__(self, awb, weight, description, flight):
        super().__init__(awb, weight, description, flight)
        self.paperwork_ok = False

    def attach_paperwork(self):
        self.paperwork_ok = True
        self.note("paperwork attached")

    def can_load(self):
        return self.paperwork_ok


class TemperatureCargo(SpecialCargo):
    def __init__(self, awb, weight, description, flight, low, high):
        super().__init__(awb, weight, description, flight)
        self.low = low
        self.high = high

    def check_temp(self, celsius):
        if celsius < self.low or celsius > self.high:
            self.set_status("spoiled")
            return False
        return True


class DangerousCargo(SpecialCargo):
    """Dangerous goods are held for review and are never loaded here."""
    def __init__(self, awb, weight, description, flight, un_class):
        super().__init__(awb, weight, description, flight)
        self.un_class = un_class
        self.set_status("held")

    def can_load(self):
        return False


class Flight(Record):
    """One flight on one date. A scheduled flight has `service` set."""
    def __init__(self, number, route, departure, aircraft, international=False, service=None):
        super().__init__()
        self.number = number
        self.route = route
        self.dest = route.dest
        self.departure = departure
        self.aircraft = aircraft
        self.aircraft_history = [aircraft]
        self.international = international
        self.service = service
        self.delay_minutes = 0
        self.crew = []
        self.reservations = []
        self.cargo = []
        self.baggage = []

    def arrival(self):
        return self.departure + timedelta(minutes=self.delay_minutes + self.route.minutes)

    def live_reservations(self):
        result = []
        for r in self.reservations:
            if r.is_live():
                result.append(r)
        return result

    def book(self, passenger, seat=None, connection_at=None):
        reservation = Reservation(passenger, self, seat, connection_at)
        self.reservations.append(reservation)
        return reservation

    def accept_baggage(self, reservation, tag, weight):
        bag = Baggage(tag, reservation, weight)
        self.baggage.append(bag)
        return bag

    def assign_crew(self, member):
        code = self.aircraft.type.code
        if not isinstance(member, FlightCrew):
            raise ValueError(f"{member.name} is not flight crew")
        if not member.qualified_for(code, self.departure):
            raise ValueError(f"{member.name} not qualified for {code}")
        if member.duty_left() < 120:
            raise ValueError(f"{member.name} duty limit")
        assignment = CrewAssignment(self, member)
        self.crew.append(assignment)
        return assignment

    def crew_gaps(self):
        pilots = 0
        cabin = 0
        gaps = []
        for a in self.crew:
            if a.status != "active":
                continue
            if isinstance(a.member, Pilot):
                pilots += 1
            if isinstance(a.member, CabinCrew):
                cabin += 1
            if not a.member.qualified_for(self.aircraft.type.code, self.departure):
                gaps.append(f"{a.member.name} unqualified for {self.aircraft.type.code}")
        if pilots < 2:
            gaps.append("needs 2 pilots")
        if cabin == 0:
            gaps.append("needs cabin crew")
        return gaps

    def change_aircraft(self, new_aircraft):
        """Swap the aircraft. Returns reservations whose seat does not exist on the new one."""
        if not new_aircraft.serviceable():
            raise ValueError(f"{new_aircraft.reg} not serviceable")
        self.aircraft = new_aircraft
        self.aircraft_history.append(new_aircraft)
        self.note(f"aircraft -> {new_aircraft.reg}")
        return self.drop_missing_seats()

    def drop_missing_seats(self):
        """Clear seats that no longer exist in the aircraft's current layout."""
        lost = []
        for r in self.live_reservations():
            if r.seat and not self.aircraft.config.has_seat(r.seat):
                r.note(f"seat {r.seat} missing on {self.aircraft.config.name}")
                r.seat = None
                lost.append(r)
        return lost

    def cargo_excess(self):
        total = 0
        for c in self.cargo:
            if c.status in ["accepted", "loaded"]:
                total += c.weight
        return max(0, total - self.aircraft.cargo_capacity)

    def delay(self, minutes):
        self.delay_minutes += minutes
        self.note(f"delayed {minutes} min")

    def divert(self, airport):
        self.note(f"diverted {self.dest} -> {airport}")
        self.dest = airport
        self.set_status("diverted")

    def cancel(self):
        """Cancelled flights are kept, with everything attached to them put on hold."""
        self.set_status("cancelled")
        for r in self.reservations:
            if r.is_live():
                r.set_status("flight_cancelled")
        for a in self.crew:
            a.release()
        for b in self.baggage:
            b.set_status("held")
        for c in self.cargo:
            c.set_status("held")

    def audit_documents(self):
        removed = []
        if self.international:
            for r in self.live_reservations():
                if not r.passenger.has_valid_document(self.departure):
                    r.note("travel document problem")
                    r.remove_from_flight()
                    removed.append(r)
        return removed


class CharterAgreement(Record):
    def __init__(self, customer, passengers):
        super().__init__()
        self.customer = customer
        self.passengers = passengers
        self.approved = False

    def approve(self):
        self.approved = True
        self.note("approved")

    def change_passengers(self, number):
        self.note(f"passengers {self.passengers} -> {number}")
        self.passengers = number


class CharterFlight(Flight):
    """A flight sold to a customer instead of coming from the timetable."""
    def __init__(self, number, route, departure, aircraft, agreement):
        super().__init__(number, route, departure, aircraft)
        self.agreement = agreement

    def resize(self, number):
        """Change the agreed passenger count and return the seat shortfall."""
        self.agreement.change_passengers(number)
        return max(0, number - self.aircraft.config.capacity())


class DisruptionEvent(Record):
    """A flight disruption. kind is "delay", "cancellation", "diversion" or "substitution".
    detail is the delay minutes, the diversion airport or the substitute aircraft."""
    def __init__(self, kind, flight, reason, detail=None):
        super().__init__()
        self.kind = kind
        self.flight = flight
        self.reason = reason
        self.detail = detail
        self.affected = []

    def apply(self):
        self.flight.note(f"{self.kind} event: {self.reason}")
        self.set_status("applied")
        if self.kind == "delay":
            self.flight.delay(self.detail)
            limit = self.flight.arrival() + timedelta(minutes=MIN_CONNECT)
            for r in self.flight.live_reservations():
                if r.connection_at and r.connection_at < limit:
                    self.affected.append(r)
        elif self.kind == "cancellation":
            self.affected = self.flight.live_reservations()
            self.flight.cancel()
        elif self.kind == "diversion":
            self.flight.divert(self.detail)
            self.affected = self.flight.live_reservations()
        elif self.kind == "substitution":
            self.affected = self.flight.change_aircraft(self.detail)


class RecoveryOption(Record):
    def __init__(self, label, cost):
        super().__init__()
        self.label = label
        self.cost = cost


def option_cost(option):
    return option.cost


class DisruptionPlanner(Record):
    """Suggests recovery options, cheapest first."""
    def options_for(self, inbound, later_flights):
        options = [RecoveryOption("Swap crews", 50)]
        for f in later_flights:
            waiting = len(f.live_reservations())
            options.append(RecoveryOption(f"Hold {f.number}", inbound.delay_minutes * waiting))
            options.append(RecoveryOption(f"Cancel {f.number}", waiting * 200))
        options.sort(key=option_cost)
        return options

    def choose(self, option):
        option.set_status("chosen")
        return option


class Airline(Record):
    def __init__(self, name):
        super().__init__()
        self.name = name
        self.flights = []

    def add_flight(self, flight):
        self.flights.append(flight)
        return flight

    def retire_aircraft(self, aircraft, now):
        """Retire an aircraft and return the future flights that were planned around it."""
        aircraft.retire()
        stranded = []
        for f in self.flights:
            if f.aircraft is aircraft and f.departure > now and f.status == "active":
                f.note(f"aircraft {aircraft.reg} retired, needs substitute")
                stranded.append(f)
        return stranded

    def end_of_day_report(self):
        lines = []
        for f in self.flights:
            regs = ">".join([a.reg for a in f.aircraft_history])
            lines.append(f"{f.number} [{f.status}] aircraft {regs}, live pax {len(f.live_reservations())}")
            for h in f.history[1:]:
                lines.append(f"    {h}")
            for r in f.reservations:
                if len(r.history) > 2:
                    lines.append(f"    pax {r.passenger.name}: {r.status}; " + "; ".join(r.history[1:]))
        return "\n".join(lines)


def make_seats(rows, letters):
    seats = set()
    for row in rows:
        for letter in letters:
            seats.add(f"{row}{letter}")
    return seats


def make_qualification(code):
    return Qualification(code, datetime(2027, 12, 31))


def make_passenger(name):
    passenger = Passenger(name)
    passenger.add_document(TravelDocument(f"PK-{name}", datetime(2030, 1, 1)))
    return passenger


def section(title):
    print(f"\n=== {title} ===")


def main():
    a320 = AircraftType("A320", "Airbus A320")
    atr = AircraftType("AT72", "ATR 72")
    first_class_seats = make_seats(range(1, 4), "ABCD")
    full = CabinConfiguration("A320-2class", first_class_seats.union(make_seats(range(4, 31), "ABCDEF")))
    dense = CabinConfiguration("A320-dense", make_seats(range(4, 36), "ABCDEF"))
    atr_cfg = CabinConfiguration("ATR-70", make_seats(range(1, 18), "ABCD"))

    a1 = Aircraft("AP-A1", a320, full, 2000)
    a2 = Aircraft("AP-A2", a320, dense, 1500)
    a3 = Aircraft("AP-A3", a320, dense, 1500)
    a4 = Aircraft("AP-A4", a320, full, 2000)
    t1 = Aircraft("AP-T1", atr, atr_cfg, 800)

    lhe = Airport("LHE", "Lahore")
    khi = Airport("KHI", "Karachi")
    isb = Airport("ISB", "Islamabad")
    dxb = Airport("DXB", "Dubai")
    lhe_khi = Route(lhe, khi, 105)
    khi_isb = Route(khi, isb, 120)
    lhe_dxb = Route(lhe, dxb, 200)

    pk301 = ScheduledService("PK301", lhe_khi, time(5, 30))
    pk302 = ScheduledService("PK302", khi_isb, time(14, 0))
    pk303 = ScheduledService("PK303", lhe_khi, time(18, 0))
    pk741 = ScheduledService("PK741", lhe_dxb, time(9, 0))
    day = datetime(2026, 10, 22).date()

    air = Airline("Regional Air")
    f301 = air.add_flight(pk301.fly_on(day, a1))
    f302 = air.add_flight(pk302.fly_on(day, a1))
    f303 = air.add_flight(pk303.fly_on(day, a4))
    f741 = air.add_flight(pk741.fly_on(day, a4, international=True))

    ali = Pilot("Ali", "Captain")
    sana = Pilot("Sana", "First Officer")
    hina = Pilot("Hina", "First Officer")
    omar = Pilot("Omar", "Captain")
    zoya = CabinCrew("Zoya", "Cabin Crew")
    kamran = EngineeringStaff("Kamran", "Engineer")
    imran = GroundStaff("Imran", "Check-in Agent")
    for member in [ali, sana, hina, zoya]:
        member.add_qualification(make_qualification("A320"))
    omar.add_qualification(make_qualification("AT72"))

    ayesha = make_passenger("Ayesha")
    hamza = make_passenger("Hamza")
    sara = make_passenger("Sara")
    usman = make_passenger("Usman")
    noor = make_passenger("Noor")

    ayesha_res = f301.book(ayesha, "1A")
    hamza_res = f301.book(hamza, "12C")
    sara_res = f301.book(sara, "2B")
    usman_res = f301.book(usman, "20F", connection_at=datetime(2026, 10, 22, 8, 30))
    f302.book(hamza, "10A")
    f302.book(usman, "10B")

    section("1. Fault before departure: aircraft changes twice, with a different layout")
    a1.report_defect("hydraulic leak")
    print("A1 serviceable:", a1.serviceable())
    try:
        f301.change_aircraft(a1)
    except ValueError as e:
        print("rejected:", e)
    event = DisruptionEvent("substitution", f301, "A1 defect", a2)
    event.apply()
    print("seats lost:", event.affected)
    event.affected[0].assign_seat("4A")
    event.affected[1].assign_seat("4B")
    print("booked on", ayesha_res.booked_config, "now on", f301.aircraft.config.name)
    a2.schedule_work("brake check", datetime(2026, 10, 22, 14, 0))
    due = a2.work_due_before(datetime(2026, 10, 22, 18, 0))
    print("A2 work due before 18:00:", [w.description for w in due])
    a2.inspect("walkaround").record(False, "tyre damage")
    f301.change_aircraft(a3)
    parts = Cargo("AWB-100", 1700, "machine parts", f301)
    print("aircraft history:", [a.reg for a in f301.aircraft_history], "cargo excess kg:", f301.cargo_excess())

    section("2. Defect decision: repair, defer, return to service")
    a1.ground()
    kamran.sign_off(a1.defects[0])
    a1.return_to_service()
    print("A1 after sign-off:", a1.status, "| serviceable:", a1.serviceable())
    print("A2 serviceable with open tyre defect:", a2.serviceable())
    a2.defects[0].defer()
    print("A2 serviceable after deferral:", a2.serviceable())
    a2.work[0].complete()
    print("A2 work still due:", len(a2.work_due_before(datetime(2026, 10, 22, 18, 0))))

    section("3. Crew qualification, duty limit and role history")
    f301.assign_crew(ali)
    f301.assign_crew(sana)
    f301.assign_crew(zoya)
    for member in [omar, hina, kamran]:
        try:
            f301.assign_crew(member)
        except ValueError as e:
            print("rejected:", e)
    hina.log_duty(500)
    try:
        f301.assign_crew(hina)
    except ValueError as e:
        print("rejected:", e)
    before = datetime(2026, 10, 1)
    after = datetime(2026, 10, 23)
    sana.promote("Captain", datetime(2026, 10, 15))
    ali.add_role("Instructor", datetime(2026, 10, 1))
    zoya.make_senior(datetime(2026, 10, 10))
    print("Sana before/after:", sana.roles_on(before), sana.roles_on(after))
    print("Sana role on PK301 assignment:", f301.crew[1].role_at_time, "| Ali:", ali.roles_on(after))
    print("Zoya roles:", zoya.roles_on(after))
    hina.qualifications[0].revoke(datetime(2026, 10, 22, 12, 0))
    print("Hina qualified at PK301 departure:", hina.qualified_for("A320", f301.departure),
          "| at PK303 departure:", hina.qualified_for("A320", f303.departure))
    print("crew gaps:", f301.crew_gaps())

    section("4. Check-in and boarding, then a passenger removed after check-in")
    imran.check_in_passenger(ayesha_res)
    ayesha_res.board()
    print("Ayesha:", ayesha_res.status)
    noor_res = f741.book(noor, "5C")
    noor_res.add_request("mobility").fulfil()
    imran.check_in_passenger(noor_res)
    noor_bag = f741.accept_baggage(noor_res, "TAG-9", 18)
    imran.handle_bag(noor_bag)
    noor.documents[0].flag()
    removed = f741.audit_documents()
    print(removed, "| bag:", noor_bag.status, "| checkin:", noor_res.checkin.status)
    try:
        noor_res.check_in()
    except ValueError as e:
        print("re-check-in rejected:", e)

    section("5. Bag on a different routing, then damaged")
    bag2 = f301.accept_baggage(hamza_res, "TAG-7", 22)
    bag2.route_via(f302)
    print("routing mismatch:", bag2.routing_mismatch())
    claim = bag2.damaged("handle torn")
    claim.settle()
    print(bag2.status, "->", claim.status, [f.number for f in claim.routing])

    section("6. Cargo accepted, later dangerous or temperature failure")
    parts.load()
    parts.deliver()
    print("AWB-100:", parts.status)
    lab = Cargo("AWB-200", 120, "lab supplies", f301)
    lab.load()
    dangerous = lab.as_dangerous("UN3480")
    dangerous.attach_paperwork()
    try:
        dangerous.load()
    except ValueError as e:
        print("rejected:", e)
    print(lab.status, "->", dangerous.status, "| is special cargo:", isinstance(dangerous, SpecialCargo))
    vaccines = TemperatureCargo("AWB-300", 40, "vaccines", f301, 2, 8)
    print("temp ok at 12C:", vaccines.check_temp(12), vaccines.status)

    section("7. Delayed inbound threatens later flights")
    delay = DisruptionEvent("delay", f301, "late inbound aircraft", 180)
    delay.apply()
    print("missed connections:", delay.affected)
    planner = DisruptionPlanner()
    options = planner.options_for(f301, [f302, f303])
    print([(o.label, o.cost) for o in options])
    planner.choose(options[0])
    new_res = delay.affected[0].rebook(f303, "8A")
    print("rebooked:", new_res, "| old:", delay.affected[0].status)

    section("8. Cabin reconfiguration after bookings exist")
    sara_f303 = f303.book(sara, "2C")
    a4.reconfigure(dense)
    lost = f303.drop_missing_seats()
    print("Sara booked on", sara_f303.booked_config, "| aircraft now", a4.config.name, "| seat lost:", lost)
    print("A4 config history:", a4.config_history)

    section("9. Restriction, diversion, retirement, cancellation, charter change")
    fog = AirportRestriction(khi, "fog", datetime(2026, 10, 22, 6, 0))
    khi.add_restriction(fog)
    fog.lift(datetime(2026, 10, 22, 10, 0))
    print("at 08:00:", len(khi.restrictions_at(datetime(2026, 10, 22, 8, 0))),
          "| at 12:00:", len(khi.restrictions_at(datetime(2026, 10, 22, 12, 0))))
    DisruptionEvent("diversion", f303, "KHI fog", isb).apply()
    stranded = air.retire_aircraft(a1, datetime(2026, 10, 21))
    print("stranded by retirement:", [f.number for f in stranded])
    DisruptionEvent("cancellation", f302, "no aircraft").apply()
    print("cancelled flight keeps pax:", [(r.passenger.name, r.status) for r in f302.reservations])
    agreement = CharterAgreement("Acme Corp", 40)
    charter = air.add_flight(CharterFlight("CH900", lhe_dxb, datetime(2026, 10, 22, 20, 0), t1, agreement))
    charter.agreement.approve()
    print("charter shortfall for 90 pax:", charter.resize(90))

    section("End-of-day report")
    print(air.end_of_day_report())


if __name__ == "__main__":
    main()
