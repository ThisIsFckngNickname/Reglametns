import React, { useState, useEffect } from 'react';
import { listProfiles } from '../api/client';
import type { CompanyProfile } from '../types';

interface ProfileSelectorProps {
  selectedProfileId: string | null;
  onChange: (profileId: string | null) => void;
  disabled?: boolean;
}

export default function ProfileSelector({
  selectedProfileId,
  onChange,
  disabled,
}: ProfileSelectorProps) {
  const [profiles, setProfiles] = useState<CompanyProfile[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    listProfiles({ status: 'ready' })
      .then((data) => setProfiles(data.items))
      .catch(() => {
        // silently fail — selector just stays empty
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="form-group">
      <label htmlFor="profile-select">Профиль компании (опционально)</label>
      <select
        id="profile-select"
        className="input-field"
        value={selectedProfileId || ''}
        onChange={(e) => onChange(e.target.value || null)}
        disabled={disabled || loading}
      >
        <option value="">Без профиля</option>
        {profiles.map((p) => (
          <option key={p.profile_id} value={p.profile_id}>
            {p.name} ({p.document_count} док.)
          </option>
        ))}
      </select>
    </div>
  );
}
