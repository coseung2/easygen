with f as (
  select family_id from public.children where id = '0e414a95-e5b4-460d-9a4e-09f8c2034d52'
)
select m.id,
       (m.captured_at at time zone 'Asia/Seoul') as captured_kst,
       m.caption,
       m.place_label,
       m.together_with,
       (select count(*) from public.reactions r where r.moment_id = m.id) as hearts,
       (select count(*) from public.comments c where c.moment_id = m.id) as comments,
       (select json_agg(json_build_object(
                 'kind', a.kind, 'type', a.content_type, 'bytes', a.byte_length,
                 'w', a.width, 'h', a.height, 'pos', a.position,
                 'provider', a.storage_provider, 'path', a.object_path)
               order by a.position, a.kind)
          from public.moment_assets a
         where a.moment_id = m.id and a.processing_status = 'ready') as assets
  from public.moments m
  join f using (family_id)
 where m.status = 'ready'
 order by m.captured_at
