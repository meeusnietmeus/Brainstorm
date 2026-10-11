-- Saved pan and zoom of a space's canvas: {"x": float, "y": float, "scale": float}
ALTER TABLE spaces ADD COLUMN view_state TEXT CHECK (view_state IS NULL OR json_valid(view_state));
