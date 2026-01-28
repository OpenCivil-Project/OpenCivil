-- Make the videos bucket public so videos can be accessed on the website
UPDATE storage.buckets SET public = true WHERE id = 'videos';

-- Allow anyone to view videos (public read access)
CREATE POLICY "Public can view videos"
ON storage.objects
FOR SELECT
TO public
USING (bucket_id = 'videos');