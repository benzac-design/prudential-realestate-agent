-- Run this SQL in your Supabase SQL editor to set up the database

-- Leads table
create table if not exists leads (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  email text not null,
  phone text not null,
  message text,
  budget text,
  timeline text,
  pre_approved boolean,
  status text default 'new',
  agent_id text not null,
  created_at timestamptz default now()
);

-- Follow-up schedules
create table if not exists followup_schedules (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid references leads(id),
  agent_id text not null,
  send_at timestamptz not null,
  message text not null,
  channel text default 'sms',
  sent boolean default false,
  created_at timestamptz default now()
);

-- Buyer clients for weekly updates
create table if not exists buyer_clients (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  email text not null,
  agent_id text not null,
  agent_name text,
  min_beds integer default 2,
  max_price integer default 500000,
  areas text,
  property_type text default 'any',
  created_at timestamptz default now()
);

-- Saved listings
create table if not exists listings (
  id uuid primary key default gen_random_uuid(),
  agent_id text not null,
  address text not null,
  bedrooms integer,
  bathrooms numeric,
  sqft integer,
  price integer,
  features text,
  neighborhood text,
  description text,
  created_at timestamptz default now()
);
