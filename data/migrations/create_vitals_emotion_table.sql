-- Migration: Create vitals_emotion table
-- This table stores emotion predictions from vitals/biometric data
-- Similar structure to face_emotion and voice_emotion tables

CREATE TABLE IF NOT EXISTS public.vitals_emotion (
  id integer NOT NULL DEFAULT nextval('vitals_emotion_id_seq'::regclass),
  user_id uuid NOT NULL,
  timestamp timestamp without time zone NOT NULL,
  predicted_emotion character varying NOT NULL CHECK (predicted_emotion::text = ANY (ARRAY['Angry'::character varying::text, 'Sad'::character varying::text, 'Happy'::character varying::text, 'Fear'::character varying::text])),
  emotion_confidence double precision NOT NULL CHECK (emotion_confidence >= 0::double precision AND emotion_confidence <= 1::double precision),
  -- Optional: Store raw vitals data if needed
  heart_rate double precision,
  heart_rate_variability double precision,
  skin_temperature double precision,
  respiration_rate double precision,
  eda double precision,
  -- Metadata
  is_synthetic boolean DEFAULT false,
  CONSTRAINT vitals_emotion_pkey PRIMARY KEY (id),
  CONSTRAINT vitals_emotion_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id)
);

-- Create sequence if it doesn't exist
CREATE SEQUENCE IF NOT EXISTS public.vitals_emotion_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.vitals_emotion_id_seq OWNED BY public.vitals_emotion.id;

-- Create index on user_id and timestamp for faster queries
CREATE INDEX IF NOT EXISTS idx_vitals_emotion_user_timestamp ON public.vitals_emotion(user_id, timestamp);

-- Add comment
COMMENT ON TABLE public.vitals_emotion IS 'Stores emotion predictions derived from vitals/biometric sensor data';

