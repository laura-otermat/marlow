-- Marlow schema: households, their members, and the memories they share.
--
-- Every table has row-level security enabled. End users can read their own
-- households and read/write memories in households they belong to. Household
-- and membership writes are performed only by the trusted API server using
-- the Supabase service role, so no end-user write policies exist for them.

create table if not exists public.households (
    id uuid primary key default gen_random_uuid(),
    name text not null check (length(trim(name)) between 1 and 120),
    created_by_user_id uuid references auth.users(id) on delete set null,
    created_at timestamptz not null default now()
);

create table if not exists public.household_members (
    id uuid primary key default gen_random_uuid(),
    household_id uuid not null references public.households(id) on delete cascade,
    user_id uuid not null references auth.users(id) on delete cascade,
    role text not null default 'member' check (role in ('owner', 'member')),
    created_at timestamptz not null default now(),
    unique (household_id, user_id)
);

create table if not exists public.memories (
    id uuid primary key default gen_random_uuid(),
    household_id uuid not null references public.households(id) on delete cascade,
    created_by_user_id uuid references auth.users(id) on delete set null,
    category text not null,
    subject text not null,
    value text not null,
    confidence double precision,
    created_at timestamptz not null default now()
);

create index if not exists household_members_user_role_idx
    on public.household_members (user_id, role, household_id);

create index if not exists memories_household_created_at_idx
    on public.memories (household_id, created_at desc);

create index if not exists memories_created_by_user_idx
    on public.memories (created_by_user_id);

alter table public.households enable row level security;
alter table public.household_members enable row level security;
alter table public.memories enable row level security;

-- Households -----------------------------------------------------------------

create policy "households_are_visible_to_members"
    on public.households
    for select
    using (
        exists (
            select 1
            from public.household_members
            where household_members.household_id = households.id
              and household_members.user_id = auth.uid()
        )
    );

-- Household members ----------------------------------------------------------

create policy "household_members_are_visible_to_members"
    on public.household_members
    for select
    using (user_id = auth.uid());

-- Memories -------------------------------------------------------------------

create policy "users_can_view_memories_in_their_households"
    on public.memories
    for select
    using (
        household_id in (
            select household_id
            from public.household_members
            where user_id = auth.uid()
        )
    );

create policy "users_can_insert_memories_in_their_households"
    on public.memories
    for insert
    with check (
        household_id in (
            select household_id
            from public.household_members
            where user_id = auth.uid()
        )
        and created_by_user_id = auth.uid()
    );

create policy "users_can_update_memories_in_their_households"
    on public.memories
    for update
    using (
        household_id in (
            select household_id
            from public.household_members
            where user_id = auth.uid()
        )
    )
    with check (
        household_id in (
            select household_id
            from public.household_members
            where user_id = auth.uid()
        )
    );

create policy "users_can_delete_memories_in_their_households"
    on public.memories
    for delete
    using (
        household_id in (
            select household_id
            from public.household_members
            where user_id = auth.uid()
        )
    );
