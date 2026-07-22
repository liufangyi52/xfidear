export interface AudienceMessages {
  county_admin: string
  resident: string
  tourist: string
  village_officer: string
  scenic_manager: string
}

export interface Alert {
  id: number
  title: string
  disaster_type: string
  level: string
  affected_areas: string[]
  started_at: string
  duration: string
  advice: string
  status: string
  data_source_note: string
  audience_messages: AudienceMessages
  created_at?: string
  is_pushed: boolean
  pushed_at?: string | null
}

export interface Shelter {
  id: string
  name: string
  area: string
  lat: number
  lng: number
  capacity: number
  contact: string
  source: string
}

export interface RiskPoint {
  id: string
  name: string
  district: string
  scenic_area: string
  lat: number
  lng: number
  slope: number
  risk_level: string
  warning_color: string
  risk_score: number
  action: string
  guide_target: string
  nearby_shelter: {
    id: string
    name: string
    lat: number
    lng: number
    capacity: number
    distance_km: number
  }
  heat_weight: number
}

export type Role = 'city_admin' | 'county_admin' | 'community_admin' | 'resident' | 'tourist'

export interface User {
  id: number
  username: string
  role: Role
  district?: string
  community?: string
}

export interface DispatchMessage {
  id: number
  title: string
  content: string
  sender_role: Role
  sender_id: number
  priority: 'city' | 'county' | 'community' | 'normal'
  target_roles: Role[]
  target_district?: string
  target_community?: string
  target_user_id?: number | null
  source_type?: string
  related_id?: number | null
  parent_id?: number | null
  status?: string
  reply_content?: string
  review_note?: string
  reviewed_by?: number | null
  reviewed_at?: string | null
  attachments?: Array<{
    id: string
    name: string
    size: number
    content_type?: string
    url: string
  }>
  created_at: string
}

export type IncidentType = 'flood' | 'landslide' | 'road' | 'medical' | 'sos' | 'shelter' | 'other'
export type IncidentStatus = 'pending' | 'responding' | 'resolved'
export type IncidentSeverity = 'low' | 'medium' | 'high' | 'critical'

export interface Incident {
  id: number
  type: IncidentType
  description: string
  lat: number
  lng: number
  district?: string
  scenic_area?: string
  severity: IncidentSeverity
  status: IncidentStatus
  reporter_role: Role
  reporter_id?: number
  community?: string
  source_title?: string
  source_org?: string
  source_url?: string
  source_date?: string
  workflow_steps?: string[]
  need_review?: boolean
  is_demo?: boolean
  nearest_shelter?: {
    id: string
    name: string
    area: string
    lat: number
    lng: number
    capacity: number
    distance_km: number
  }
  created_at: string
  resolved_at?: string | null
}
