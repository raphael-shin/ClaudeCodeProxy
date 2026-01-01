import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import PageHeader from '@/components/PageHeader';
import { api, AccessKey, User } from '@/lib/api';

const inputClass =
  'w-full rounded-xl border border-line bg-surface px-4 py-2 text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20';

export default function UserDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);
  const [keys, setKeys] = useState<AccessKey[]>([]);
  const [pendingKey, setPendingKey] = useState<{ value: string; label: string } | null>(
    null
  );
  const [copied, setCopied] = useState(false);
  const [bedrockKey, setBedrockKey] = useState('');
  const [selectedKeyId, setSelectedKeyId] = useState<string | null>(null);
  const [notice, setNotice] = useState('');

  const showNotice = (message: string) => {
    setNotice(message);
    setTimeout(() => setNotice(''), 2500);
  };

  useEffect(() => {
    if (!id) return;
    api.getUser(id).then(setUser);
    api.getAccessKeys(id).then(setKeys);
  }, [id]);

  const activeKeys = useMemo(
    () => keys.filter((key) => key.status === 'active').length,
    [keys]
  );
  const revokedKeys = keys.length - activeKeys;
  const selectedKey = useMemo(
    () => keys.find((key) => key.id === selectedKeyId) || null,
    [keys, selectedKeyId]
  );

  const handleIssueKey = async () => {
    if (!id) return;
    const key = await api.createAccessKey(id, { bedrock_region: 'ap-northeast-2' });
    if (key.raw_key) {
      setPendingKey({ value: key.raw_key, label: 'New key issued' });
      setCopied(false);
    }
    const { raw_key, ...safeKey } = key;
    setKeys((prev) => [{ ...safeKey, has_bedrock_key: false }, ...prev]);
  };

  const handleRevoke = async (keyId: string) => {
    await api.revokeAccessKey(keyId);
    setKeys((prev) =>
      prev.map((k) =>
        k.id === keyId ? { ...k, status: 'revoked', has_bedrock_key: false } : k
      )
    );
  };

  const handleRegisterBedrock = async () => {
    if (selectedKey?.has_bedrock_key) {
      showNotice('Bedrock key is already linked.');
      return;
    }
    if (selectedKeyId && bedrockKey) {
      await api.registerBedrockKey(selectedKeyId, bedrockKey);
      setBedrockKey('');
      setKeys((prev) =>
        prev.map((k) =>
          k.id === selectedKeyId ? { ...k, has_bedrock_key: true } : k
        )
      );
      setSelectedKeyId(null);
      showNotice('Bedrock key registered.');
    }
  };

  const handleDeactivate = async () => {
    if (!id) return;
    await api.deactivateUser(id);
    navigate('/users');
  };

  const handleCopyPendingKey = async () => {
    if (!pendingKey?.value) return;
    const copySucceeded = await copyToClipboard(pendingKey.value);
    if (copySucceeded) {
      setCopied(true);
      showNotice('Key copied to clipboard.');
      setTimeout(() => setCopied(false), 2000);
      return;
    }
    showNotice('Copy failed. Try again.');
  };

  if (!user) {
    return (
      <div className="rounded-2xl border border-line bg-surface p-8 text-sm text-muted">
        Loading user...
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Users"
        title={user.name}
        subtitle={user.description || 'No description'}
        actions={
          <>
            <Link
              to="/users"
              className="rounded-full border border-line px-4 py-2 text-sm font-semibold text-ink transition hover:bg-surface-2"
            >
              Back to Users
            </Link>
            <span
              className={[
                'inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold',
                user.status === 'active' ? 'bg-success/10 text-success' : 'bg-danger/10 text-danger',
              ].join(' ')}
            >
              {user.status}
            </span>
            {user.status === 'active' && (
              <button
                onClick={handleDeactivate}
                className="rounded-full bg-danger px-4 py-2 text-sm font-semibold text-white shadow-soft transition hover:bg-red-600"
              >
                Deactivate
              </button>
            )}
          </>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <div className="rounded-2xl border border-line bg-surface p-6 shadow-soft">
          <h2 className="text-lg font-semibold text-ink">Profile</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2 text-sm">
            <Detail label="User ID" value={user.id} mono />
            <Detail label="Created" value={formatDate(user.created_at)} />
            <Detail label="Updated" value={formatDate(user.updated_at)} />
            <Detail label="Status" value={user.status} />
          </div>
        </div>
        <div className="rounded-2xl border border-line bg-surface p-6 shadow-soft">
          <h2 className="text-lg font-semibold text-ink">Access Summary</h2>
          <div className="mt-4 space-y-3 text-sm text-muted">
            <SummaryRow label="Total keys" value={keys.length} />
            <SummaryRow label="Active keys" value={activeKeys} />
            <SummaryRow label="Revoked keys" value={revokedKeys} />
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-line bg-surface p-6 shadow-soft">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-ink">Access Keys</h2>
            <p className="text-xs text-muted">Issue, revoke, and register Bedrock keys.</p>
          </div>
          {user.status === 'active' && (
            <button
              onClick={handleIssueKey}
              className="rounded-full bg-accent px-4 py-2 text-sm font-semibold text-white shadow-soft transition hover:bg-accent-strong"
            >
              Issue New Key
            </button>
          )}
        </div>

        {pendingKey && (
          <div className="mt-5 rounded-2xl border border-line bg-surface-2 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-xs uppercase tracking-[0.24em] text-muted">
                  {pendingKey.label}
                </div>
                <p className="mt-1 text-sm text-muted">
                  Copy now. The full key is never shown in the UI.
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleCopyPendingKey}
                  className="rounded-full border border-line px-3 py-1.5 text-xs font-semibold text-ink transition hover:bg-surface"
                >
                  {copied ? 'Copied' : 'Copy'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setPendingKey(null);
                    setCopied(false);
                  }}
                  className="rounded-full border border-line px-3 py-1.5 text-xs font-semibold text-ink transition hover:bg-surface"
                >
                  Dismiss
                </button>
              </div>
            </div>
          </div>
        )}

        {selectedKeyId && (
          <div className="mt-5 rounded-2xl border border-line bg-surface-2 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-xs uppercase tracking-[0.24em] text-muted">
                  Register Bedrock API Key
                </div>
                <p className="mt-1 text-sm text-muted">
                  Attach Bedrock credentials to this access key.
                </p>
                {selectedKey && (
                  <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted">
                    <span className="rounded-full border border-line bg-surface px-3 py-1">
                      Key {selectedKey.key_prefix}...
                    </span>
                    <span className="rounded-full border border-line bg-surface px-3 py-1">
                      Region {selectedKey.bedrock_region}
                    </span>
                    <span className="rounded-full border border-line bg-surface px-3 py-1">
                      Created {formatDate(selectedKey.created_at)}
                    </span>
                  </div>
                )}
              </div>
              <button
                type="button"
                onClick={() => setSelectedKeyId(null)}
                className="rounded-full border border-line px-3 py-1.5 text-xs font-semibold text-ink transition hover:bg-surface"
              >
                Cancel
              </button>
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <input
                type="password"
                placeholder="Bedrock API Key"
                value={bedrockKey}
                onChange={(e) => setBedrockKey(e.target.value)}
                className={`${inputClass} max-w-xs`}
              />
              <button
                type="button"
                onClick={handleRegisterBedrock}
                className="rounded-full bg-ink px-4 py-2 text-sm font-semibold text-white transition hover:bg-black"
              >
                Register
              </button>
            </div>
          </div>
        )}

        {notice && <div className="mt-4 text-sm text-success">{notice}</div>}

        <div className="mt-6 overflow-hidden rounded-2xl border border-line">
          {keys.length === 0 ? (
            <div className="px-6 py-10 text-center text-sm text-muted">
              No access keys yet.
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-[0.2em] text-muted">
                  <th className="px-6 py-3">Prefix</th>
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3">Bedrock</th>
                  <th className="px-6 py-3">Region</th>
                  <th className="px-6 py-3">Created</th>
                  <th className="px-6 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {keys.map((key) => (
                  <tr
                    key={key.id}
                    className={[
                      'border-t border-line/60 hover:bg-surface-2',
                      selectedKeyId === key.id ? 'bg-surface-2' : '',
                    ].join(' ')}
                  >
                    <td className="px-6 py-4 font-mono text-xs text-ink">
                      {key.key_prefix}...
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={[
                          'inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold',
                          key.status === 'active'
                            ? 'bg-success/10 text-success'
                            : key.status === 'rotating'
                            ? 'bg-accent/10 text-accent'
                            : 'bg-danger/10 text-danger',
                        ].join(' ')}
                      >
                        {key.status}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      {key.has_bedrock_key ? (
                        <span className="inline-flex items-center rounded-full bg-accent/10 px-2.5 py-1 text-xs font-semibold text-accent">
                          Linked
                        </span>
                      ) : (
                        <span className="text-xs text-muted">Not set</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-muted">{key.bedrock_region}</td>
                    <td className="px-6 py-4 text-muted">
                      {formatDate(key.created_at)}
                    </td>
                    <td className="px-6 py-4 text-right">
                      {key.status === 'active' && (
                        <div className="flex items-center justify-end gap-2">
                          {!key.has_bedrock_key && (
                            <button
                              onClick={() => setSelectedKeyId(key.id)}
                              className="rounded-full border border-line px-3 py-1.5 text-xs font-semibold text-ink transition hover:bg-surface"
                            >
                              Bedrock
                            </button>
                          )}
                          <button
                            onClick={() => handleRevoke(key.id)}
                            className="rounded-full border border-line px-3 py-1.5 text-xs font-semibold text-danger transition hover:bg-surface"
                          >
                            Revoke
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

function Detail({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-[0.2em] text-muted">{label}</div>
      <div className={`mt-2 text-sm text-ink ${mono ? 'font-mono text-xs' : ''}`}>
        {value}
      </div>
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between">
      <span>{label}</span>
      <span className="text-ink">{value}</span>
    </div>
  );
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '-';
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

async function copyToClipboard(value: string) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch {
      return false;
    }
  }

  const textarea = document.createElement('textarea');
  textarea.value = value;
  textarea.style.position = 'fixed';
  textarea.style.left = '-9999px';
  document.body.appendChild(textarea);
  textarea.select();
  const copied = document.execCommand('copy');
  document.body.removeChild(textarea);
  return copied;
}
