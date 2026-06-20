-- v2: showings, lead scoring, seller leads.
-- Run this in the Supabase SQL editor (safe to run on an existing DB).

-- Booked property viewings / calls.
create table if not exists appointments (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid references leads(id) on delete cascade,
  agent_id text not null,
  scheduled_at timestamptz not null,
  location text,                       -- property address or "phone call"
  notes text,
  status text default 'scheduled',     -- scheduled | confirmed | completed | cancelled | no_show
  reminder_sent boolean default false,
  created_at timestamptz default now()
);

create index if not exists appointments_agent_idx on appointments(agent_id, scheduled_at);

-- Lead scoring + buyer/seller classification.
alter table leads add column if not exists score integer default 0;
alter table leads add column if not exists temperature text default 'cold';  -- hot | warm | cold | dead
alter table leads add column if not exists lead_type text default 'buyer';   -- buyer | seller
