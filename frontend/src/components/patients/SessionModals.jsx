import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import Modal from '../ui/Modal';
import { useFetch } from '../../hooks/useFetch';
import { patientsApi } from '../../api/patients';
import { sessionsApi } from '../../api/sessions';
import { errorText } from '../../utils/errors';

const field = 'mt-1 min-h-[44px] w-full rounded-lg border border-slate-400 px-3 text-base';
const primary = 'min-h-[44px] rounded-lg bg-brand px-4 font-semibold text-white disabled:opacity-60';
const secondary = 'min-h-[44px] rounded-lg border border-slate-300 px-4';

const num = (min, max, msg) => z.string().refine((v) => v === '' || (!Number.isNaN(Number(v)) && Number(v) >= min && Number(v) <= max), msg);
const schema = z.object({
  patient_code: z.string().regex(/^[A-Za-z0-9_-]{3,20}$/, 'Use 3 to 20 letters, numbers, dashes or underscores'),
  sex: z.enum(['', 'M', 'F', 'U']),
  birth_date: z.string(),
  gestational_age_weeks: num(20, 45, 'Enter a number from 20 to 45'),
  birth_weight_kg: num(0.3, 8, 'Enter a weight from 0.3 to 8 kg'),
});

export function PatientFormModal({ onClose, onDone }) {
  const [error, setError] = useState(null);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({ resolver: zodResolver(schema), defaultValues: { sex: '' } });
  const submit = async (v) => {
    setError(null);
    try {
      await patientsApi.create({
        patient_code: v.patient_code,
        sex: v.sex || null,
        birth_date: v.birth_date || null,
        gestational_age_weeks: v.gestational_age_weeks ? Number(v.gestational_age_weeks) : null,
        birth_weight_kg: v.birth_weight_kg ? Number(v.birth_weight_kg) : null,
      });
      onDone();
    } catch (e) {
      setError(errorText(e, 'Could not register the patient. Check the details and try again.'));
    }
  };
  const err = (k) => errors[k] && <p className="mt-1 text-sm text-red-700">{errors[k].message}</p>;
  return (
    <Modal title="Register patient" onClose={onClose}>
      <form onSubmit={handleSubmit(submit)} noValidate>
        <label className="block text-sm">Patient code
          <input className={field} placeholder="NB-022" {...register('patient_code')} />
        </label>
        <p className="mt-1 text-xs text-slate-500">Use a code, not the baby's name.</p>
        {err('patient_code')}
        <label className="mt-3 block text-sm">Sex
          <select className={field} {...register('sex')}><option value="">Not recorded</option><option value="F">Female</option><option value="M">Male</option><option value="U">Unknown</option></select>
        </label>
        <label className="mt-3 block text-sm">Birth date<input type="date" className={field} {...register('birth_date')} /></label>
        <label className="mt-3 block text-sm">Gestational age (weeks)<input inputMode="numeric" className={field} {...register('gestational_age_weeks')} /></label>{err('gestational_age_weeks')}
        <label className="mt-3 block text-sm">Birth weight (kg)<input inputMode="decimal" className={field} {...register('birth_weight_kg')} /></label>{err('birth_weight_kg')}
        {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={onClose} className={secondary}>Cancel</button>
          <button disabled={isSubmitting} className={primary}>{isSubmitting ? 'Saving…' : 'Register patient'}</button>
        </div>
      </form>
    </Modal>
  );
}

export function StartSessionModal({ patient, onClose, onDone }) {
  const { data: devices, loading } = useFetch(() => sessionsApi.availableDevices());
  const [deviceId, setDeviceId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      await sessionsApi.start({ patient_id: patient.id, device_id: Number(deviceId) });
      onDone();
    } catch (e) {
      setError(errorText(e, 'Could not start the session. Try again.'));
      setBusy(false);
    }
  };
  return (
    <Modal title={`Start monitoring ${patient.patient_code}`} onClose={onClose}>
      {loading ? <p className="text-slate-500">Loading devices…</p> : !devices?.length ? (
        <p className="text-sm text-slate-700">No device is ready. A device must be active and not already in use. Ask an administrator to activate one.</p>
      ) : (
        <>
          <label className="block text-sm">Device
            <select className={field} value={deviceId} onChange={(e) => setDeviceId(e.target.value)}>
              <option value="">Choose a device</option>
              {devices.map((d) => <option key={d.id} value={d.id}>{d.device_code}{d.location && d.location !== '—' ? `, ${d.location}` : ''}</option>)}
            </select>
          </label>
          <p className="mt-2 text-xs text-slate-500">Monitoring starts now. Start the session before placing the sensors on the baby.</p>
        </>
      )}
      {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
      <div className="mt-5 flex justify-end gap-2">
        <button onClick={onClose} className={secondary}>Cancel</button>
        {devices?.length > 0 && <button onClick={save} disabled={!deviceId || busy} className={primary}>{busy ? 'Starting…' : 'Start session'}</button>}
      </div>
    </Modal>
  );
}

export function EndSessionModal({ sessionId, patientCode, onClose, onDone }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const confirm = async () => {
    setBusy(true);
    try { await sessionsApi.stop(sessionId); onDone(); } catch (e) { setError(errorText(e, 'Could not end the session. Try again.')); setBusy(false); }
  };
  return (
    <Modal title={`End monitoring for ${patientCode}?`} onClose={onClose}>
      <p className="text-sm text-slate-700">The device is freed for another patient. All readings and alerts stay in the history.</p>
      {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
      <div className="mt-5 flex justify-end gap-2">
        <button onClick={onClose} className={secondary}>Cancel</button>
        <button onClick={confirm} disabled={busy} className="min-h-[44px] rounded-lg bg-red-700 px-4 font-semibold text-white disabled:opacity-60">{busy ? 'Ending…' : 'End session'}</button>
      </div>
    </Modal>
  );
}
