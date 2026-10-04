// Shapes of the API responses the pages use. They mirror the SQL in backend/paddock/api/routes.

export interface Ref2 {
  id: string
  name: string
}

export interface RaceRef {
  year: number
  round: number
  grand_prix: string
}

export interface Meta {
  built_at: string
  sources: { name: string; version: string; licence: string; url: string }[]
  counts: Record<'seasons' | 'races' | 'drivers' | 'constructors' | 'circuits' | 'laps' | 'pit_stops', number>
  latest_race: (RaceRef & { date: string }) | null
  next_race: (RaceRef & { date: string; circuit: string }) | null
}

export interface SeasonSummary {
  year: number
  races: number
  driver_champion_id: string | null
  driver_champion: string | null
  constructor_champion_id: string | null
  constructor_champion: string | null
}

export interface SeasonRace {
  id: number
  round: number
  date: string
  grand_prix_id: string
  grand_prix: string
  abbreviation: string
  circuit_id: string
  circuit: string
  place_name: string
  country: string
  has_sprint: boolean
  winner_id: string | null
  winner: string | null
  winner_constructor_id: string | null
  winner_constructor: string | null
  pole_id: string | null
  pole: string | null
  completed: boolean
}

export interface DriverStanding {
  position: number | null
  position_text: string
  driver_id: string
  name: string
  abbreviation: string
  nationality_code: string | null
  points: number
  wins: number
  podiums: number
  poles: number
  starts: number
  constructors: Ref2[]
}

export interface ConstructorStanding {
  position: number | null
  position_text: string
  constructor_id: string
  name: string
  engine: string | null
  points: number
  wins: number
  podiums: number
  poles: number
}

export interface Season {
  year: number
  era: { name: string; engine: string; summary: string } | null
  races: SeasonRace[]
  driver_standings: DriverStanding[]
  constructor_standings: ConstructorStanding[]
  prev: number | null
  next: number | null
}

export interface Progression {
  rounds: { id: number; round: number; abbreviation: string; grand_prix: string }[]
  drivers: { id: string; name: string; points: number[]; positions: (number | null)[] }[]
  constructors: { id: string; name: string; points: number[]; positions: (number | null)[] }[]
}

export interface GridCell {
  constructor_id: string
  position_number: number | null
  position_text: string
  points: number
  grid: number | null
  fastest_lap: boolean
  pole_position: boolean
  reason_retired: string | null
  sprint_position: number | null
}

export interface ResultsGrid {
  rounds: { id: number; round: number; abbreviation: string; grand_prix: string; country_code: string }[]
  rows: { id: string; name: string; abbreviation: string; position: number | null; points: number; results: (GridCell | null)[] }[]
}

export interface Entry {
  driver_id: string
  driver: string
  abbreviation: string
  driver_number: string | null
  constructor_id: string
  constructor: string
  engine_manufacturer_id: string | null
  engine: string | null
}

export interface RaceResult extends Entry {
  position: number | null
  position_text: string
  laps: number | null
  time: string | null
  gap: string | null
  gap_laps: number | null
  reason_retired: string | null
  retirement_category: string | null
  points: number | null
  grid: number | null
  positions_gained: number | null
  pit_stops: number | null
  fastest_lap: boolean | null
  pole_position: boolean | null
  driver_of_the_day: boolean | null
  grand_slam: boolean | null
}

export interface QualifyingResult extends Entry {
  position: number | null
  position_text: string
  time: string | null
  time_millis: number | null
  q1: string | null
  q2: string | null
  q3: string | null
  gap: string | null
}

export interface RaceInfo {
  id: number
  year: number
  round: number
  date: string
  time: string | null
  official_name: string
  qualifying_format: string
  laps: number | null
  distance: number | null
  course_length: number | null
  turns: number | null
  direction: string | null
  has_sprint: boolean
  grand_prix_id: string
  grand_prix: string
  circuit_id: string
  circuit: string
  circuit_full_name: string
  place_name: string
  country: string
  circuit_layout_id: string | null
  layout_path: string | null
  drivers_championship_decider: boolean | null
}

export interface RaceDetail {
  race: RaceInfo
  results: RaceResult[]
  qualifying: QualifyingResult[]
  sprint: RaceResult[]
  pit_stops: (Entry & { stop: number; lap: number; duration: string | null; duration_ms: number | null })[]
  fastest_laps: (Entry & { position: number; lap: number | null; time: string; time_millis: number; gap: string | null })[]
  standings: { position: number; driver_id: string; driver: string; abbreviation: string; points: number; positions_gained: number | null }[]
  has_laps: boolean
  prev: RaceRef | null
  next: RaceRef | null
}

export interface RaceLaps {
  race: { id: number; year: number; round: number; grand_prix: string; laps: number; date: string }
  drivers: (Entry & { position: number | null; position_text: string; grid: number | null; laps: number; reason_retired: string | null })[]
  laps: Record<string, [number, number, number][]>
  pit_stops: { driver_id: string; stop: number; lap: number; duration_ms: number | null }[]
}

export interface Teammate {
  driver_id: string
  name: string
  abbreviation: string
  races: number
  first_year: number
  last_year: number
  quali_won: number
  quali_lost: number
  race_won: number
  race_lost: number
  points_me: number
  points_mate: number
  median_gap_pct: number | null
  gap_races: number
  constructors: string[]
}

export interface DriverTotals {
  entries: number
  starts: number
  wins: number
  podiums: number
  poles: number
  fastest_laps: number
  points: number
  championships: number
  laps: number
  grand_slams: number
  sprint_wins: number
  best_championship_position: number | null
  best_race_result: number | null
  best_grid: number | null
}

export interface DriverDetail {
  driver: DriverTotals & {
    id: string
    name: string
    full_name: string
    first_name: string
    last_name: string
    abbreviation: string | null
    permanent_number: string | null
    date_of_birth: string | null
    date_of_death: string | null
    place_of_birth: string | null
    nationality: string | null
    nationality_country: string | null
    birth_country: string | null
  }
  milestones: Record<'first_race' | 'last_race' | 'first_win' | 'last_win', RaceRef | null>
  seasons: {
    year: number
    position: number | null
    position_text: string | null
    points: number | null
    starts: number
    wins: number
    podiums: number
    poles: number
    fastest_laps: number
    constructors: Ref2[] | null
  }[]
  finishes: { outcome: string; n: number }[]
  teammates: Teammate[]
  family: { driver_id: string; name: string; type: string }[]
}

export interface DriverRow extends DriverTotals {
  id: string
  name: string
  abbreviation: string | null
  date_of_birth: string | null
  nationality: string | null
  nationality_code: string | null
  first_year: number | null
  last_year: number | null
}
