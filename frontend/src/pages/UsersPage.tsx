import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import PageHeader from '@/components/PageHeader';
import { api, User } from '@/lib/api';

const inputClass =
  'w-full rounded-xl border border-line bg-surface px-4 py-2 text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20';

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setIsLoading(true);
    api
      .getUsers()
      .then(setUsers)
      .catch(() => {})
      .finally(() => setIsLoading(false));
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Name is required.');
      return;
    }
    setError('');
    const user = await api.createUser({ name, description: description || undefined });
    setUsers((prev) => [user, ...prev]);
    setName('');
    setDescription('');
    setShowForm(false);
  };

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Admin"
        title="Users"
        subtitle="Manage user access, status, and activity from a single list."
        actions={
          <button
            type="button"
            onClick={() => {
              setShowForm((prev) => {
                if (prev) {
                  setName('');
                  setDescription('');
                }
                return !prev;
              });
              setError('');
            }}
            className="rounded-full bg-accent px-4 py-2 text-sm font-semibold text-white shadow-soft transition hover:bg-accent-strong"
          >
            {showForm ? 'Close' : 'New User'}
          </button>
        }
      />

      {showForm && (
        <form onSubmit={handleCreate} className="rounded-2xl border border-line bg-surface p-6 shadow-soft">
          <div className="grid gap-4 md:grid-cols-[minmax(0,1.1fr)_minmax(0,1.6fr)_auto] md:items-end">
            <div>
              <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted">
                Name
              </label>
              <input
                type="text"
                placeholder="User name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className={`${inputClass} mt-2`}
              />
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-[0.2em] text-muted">
                Description
              </label>
              <input
                type="text"
                placeholder="Optional description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className={`${inputClass} mt-2`}
              />
            </div>
            <div className="flex gap-3">
              <button
                type="submit"
                className="rounded-full bg-ink px-4 py-2 text-sm font-semibold text-white transition hover:bg-black"
              >
                Create
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowForm(false);
                  setError('');
                  setName('');
                  setDescription('');
                }}
                className="rounded-full border border-line px-4 py-2 text-sm font-semibold text-ink transition hover:bg-surface-2"
              >
                Cancel
              </button>
            </div>
          </div>
          {error && <div className="mt-3 text-sm text-danger">{error}</div>}
        </form>
      )}

      <div className="rounded-2xl border border-line bg-surface shadow-soft">
        <div className="border-b border-line px-6 py-4 text-sm font-semibold text-ink">
          {isLoading ? 'Loading users...' : `${users.length} users`}
        </div>
        {users.length === 0 && !isLoading ? (
          <div className="px-6 py-12 text-center text-sm text-muted">
            No users yet. Create your first user to get started.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-[0.2em] text-muted">
                <th className="px-6 py-3">User</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3">Updated</th>
                <th className="px-6 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id} className="border-t border-line/60 hover:bg-surface-2">
                  <td className="px-6 py-4">
                    <div className="font-semibold text-ink">{user.name}</div>
                    <div className="text-xs text-muted">{user.description || 'No description'}</div>
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={[
                        'inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold',
                        user.status === 'active'
                          ? 'bg-success/10 text-success'
                          : 'bg-danger/10 text-danger',
                      ].join(' ')}
                    >
                      {user.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-muted">
                    {formatDate(user.updated_at)}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <Link
                      to={`/users/${user.id}`}
                      className="rounded-full border border-line px-3 py-1.5 text-xs font-semibold text-ink transition hover:bg-surface-2"
                    >
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '-';
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}
