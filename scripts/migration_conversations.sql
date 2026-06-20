-- Two-way conversation + opt-out support.
-- Run this in the Supabase SQL editor (safe to run on an existing DB).

-- Conversation history: every inbound/outbound message tied to a lead.
create table if not exists messages (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid references leads(id) on delete cascade,
  agent_id text not null,
  direction text not null,            -- 'inbound' (from lead) or 'outbound' (from AI)
  channel text default 'sms',
  body text not null,
  created_at timestamptz default now()
);

create index if not exists messages_lead_idx on messages(lead_id, created_at);

-- Conversation/qualification state on the lead.
alter table leads add column if not exists opted_out boolean default false;
alter table leads add column if not exists conversation_stage text default 'new';
-- stages: new -> engaged -> qualifying -> qualified -> showing_requested -> not_interested
