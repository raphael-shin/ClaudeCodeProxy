import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, User } from '@/lib/api';

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [name, setName] = useState('');
  const [showForm, setShowForm] = useState(false);

  useEffect(() => {
    api.getUsers().then(setUsers).catch(() => {});
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const user = await api.createUser({ name });
    setUsers([user, ...users]);
    setName('');
    setShowForm(false);
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Users</h1>
        <div className="space-x-4">
          <Link to="/usage" className="text-blue-500">
            Usage Dashboard
          </Link>
          <button
            onClick={() => setShowForm(!showForm)}
            className="bg-blue-500 text-white px-4 py-2 rounded"
          >
            New User
          </button>
        </div>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="bg-white p-4 rounded shadow mb-6">
          <input
            type="text"
            placeholder="User name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="p-2 border rounded mr-2"
          />
          <button type="submit" className="bg-green-500 text-white px-4 py-2 rounded">
            Create
          </button>
        </form>
      )}

      <div className="bg-white rounded shadow">
        {users.map((user) => (
          <Link
            key={user.id}
            to={`/users/${user.id}`}
            className="block p-4 border-b hover:bg-gray-50"
          >
            <div className="flex justify-between">
              <span className="font-medium">{user.name}</span>
              <span
                className={`text-sm ${user.status === 'active' ? 'text-green-500' : 'text-gray-500'}`}
              >
                {user.status}
              </span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
