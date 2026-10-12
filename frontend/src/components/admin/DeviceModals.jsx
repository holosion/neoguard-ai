import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import Modal from '../ui/Modal';
import { useFetch } from '../../hooks/useFetch';
import { adminApi } from '../../api/admin';

const detail = (e, fallback) => e?.response?.data?.detail ?? fallback;

const field = 'mt-1 min-h-[44px] w-full rounded-lg border border-slate-400 px-3 text-base';
const primary = 'min-h-[44px] rounded-lg bg-brand px-4 font-semibold text-white disabled:opacity-60';
const secondary = 'min-h-[44px] rounded-lg border border-slate-300 px-4';

const schema = z.object({
  device_code: z.string().regex(/^[A-Za-z0-9_-]{3,30}$/, 'Use 3 to 30 letters, numbers, dashes or underscores, for example DEV-001'),
  name: z.string().min(1, 'Enter a name'),
  location: z.string().min(1, 'Enter a location'),
  clinic_id: z.string().optional(),
  status: z.enum(['inactive', 'active', 'maintenance']).optional(),
});

// Register a new device, or edit one when `device` is given.
export function DeviceFormModal({ device, onClose, onDone }) {
  const [error, setError] = useState(null);
  const { data: clinics } = useFetch(() => adminApi.getClinics());
  const [secret, setSecret] = useState(null);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(schema),
    defaultValues: { device_code: device?.device_code ?? '', name: device?.name ?? '', location: device?.location ?? '', status: device?.status ?? 'inactive', clinic_id: '' },
  });
  const submit = async (values) => {
    setError(null);
    try {
      if (device) {
        await adminApi.updateDevice(device.id, { name: values.name, location: values.location, status: values.status });
        onDone();
      } else {
        if (!values.clinic_id) { setError('Choose a clinic.'); return; }
        const res = await adminApi.registerDevice({ ...values, clinic_id: Number(values.clinic_id) });
        if (res.data?.device_secret) setSecret(res.data.device_secret);
        else onDone();
      }
    } catch (e) {
      setError(detail(e, 'Could not save the device. Check the details and try again.'));
    }
  };
  if (secret) {
    return (
      <Modal title="Device registered" onClose={onDone}>
        <p className="text-sm text-slate-700">Copy this secret into the device firmware now. It is shown only once. If you lose it, rotate the secret for this device.</p>
        <code className="mt-3 block break-all rounded-lg bg-slate-100 p-3 text-sm">{secret}</code>
        <div className="mt-5 flex justify-end gap-2">
          <button onClick={() => navigator.clipboard?.writeText(secret)} className={secondary}>Copy secret</button>
          <button onClick={onDone} className={primary}>I have saved it</button>
        </div>
      </Modal>
    );
  }
  return (
    <Modal title={device ? `Edit ${device.device_code}` : 'Register new device'} onClose={onClose}>
      <form onSubmit={handleSubmit(submit)} noValidate>
        <label className="block text-sm">Device code
          <input className={`${field} ${device ? 'bg-slate-100' : ''}`} readOnly={!!device} placeholder="DEV-007" {...register('device_code')} />
        </label>
        {errors.device_code && <p className="mt-1 text-sm text-red-700">{errors.device_code.message}</p>}
        <label className="mt-3 block text-sm">Name
          <input className={field} {...register('name')} />
        </label>
        {errors.name && <p className="mt-1 text-sm text-red-700">{errors.name.message}</p>}
        <label className="mt-3 block text-sm">Location
          <input className={field} {...register('location')} />
        </label>
        {device && <label className="mt-3 block text-sm">Status<select className={field} {...register('status')}><option value="inactive">Inactive</option><option value="active">Active</option><option value="maintenance">Maintenance</option></select></label>}
        {!device && <label className="mt-3 block text-sm">Clinic
          <select className={field} {...register('clinic_id')}><option value="">Choose a clinic</option>{clinics?.map((clinic) => <option key={clinic.id} value={clinic.id}>{clinic.name}</option>)}</select>
        </label>}
        {errors.location && <p className="mt-1 text-sm text-red-700">{errors.location.message}</p>}
        {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={onClose} className={secondary}>Cancel</button>
          <button disabled={isSubmitting} className={primary}>{device ? 'Save changes' : 'Register device'}</button>
        </div>
      </form>
    </Modal>
  );
}

// Starts a session for a patient on this device at the server's current time.
export function AssignDeviceModal({ device, onClose, onDone }) {
  const { data: patients, loading } = useFetch(() => adminApi.getUnassignedPatients());
  const availablePatients = (patients ?? []).filter((patient) => patient.clinic_id === device.clinic_id);
  const [patientId, setPatientId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      await adminApi.assignDevice(device.id, { patient_id: Number(patientId) });
      onDone();
    } catch (e) {
      setError(detail(e, 'Could not start the session. Try again.'));
      setBusy(false);
    }
  };

  return (
    <Modal title={`Assign ${device.device_code} to a patient`} onClose={onClose}>
      {loading ? <p className="text-slate-500">Loading patients…</p> : !availablePatients.length ? (
        <p className="text-slate-600">No patients are waiting for a device. Register the patient first, then assign the device.</p>
      ) : (
        <>
          <label className="block text-sm">Patient
            <select className={field} value={patientId} onChange={(e) => setPatientId(e.target.value)}>
              <option value="">Choose a patient</option>
              {availablePatients.map((p) => <option key={p.id} value={p.id}>{p.patient_code}</option>)}
            </select>
          </label>
        </>
      )}
      {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
      <div className="mt-5 flex justify-end gap-2">
        <button onClick={onClose} className={secondary}>Cancel</button>
        {availablePatients.length > 0 && <button onClick={save} disabled={!patientId || busy} className={primary}>{busy ? 'Saving…' : 'Start session'}</button>}
      </div>
    </Modal>
  );
}

export function DecommissionModal({ device, onClose, onDone }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const confirm = async () => {
    setBusy(true);
    try { await adminApi.decommissionDevice(device.id); onDone(); } catch (e) { setError(detail(e, 'Could not decommission the device. Try again.')); setBusy(false); }
  };
  return (
    <Modal title={`Decommission ${device.device_code}?`} onClose={onClose}>
      <p className="text-sm text-slate-700">The device will be retired and its session ended. All readings it recorded stay in the history.</p>
      {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
      <div className="mt-5 flex justify-end gap-2">
        <button onClick={onClose} className={secondary}>Cancel</button>
        <button onClick={confirm} disabled={busy} className="min-h-[44px] rounded-lg bg-red-700 px-4 font-semibold text-white disabled:opacity-60">{busy ? 'Saving…' : 'Decommission'}</button>
      </div>
    </Modal>
  );
}
