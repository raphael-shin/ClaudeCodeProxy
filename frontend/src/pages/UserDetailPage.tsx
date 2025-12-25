import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api, AccessKey, User } from '@/lib/api';

export default function UserDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);
  const [keys, setKeys] = useState<AccessKey[]>([]);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [bedrockKey, setBedrockKey] = useState('');
  const [selectedKeyId, setSelectedKeyId] = useState<string | null>(null);

  useEffect(() => {
    if (id) {
      api.getUser(id).then(setUser);
      api.getAccessKeys(id).then(setKeys);
    }
  }, [id]);

  const handleIssueKey = async () => {
    if (!id) return;
    const key = await api.createAccessKey(id, { bedrock_region: 'ap-northeast-2' });
    setNewKey(key.raw_key || null);
    setKeys([key, ...keys]);
  };

  const handleRevoke = async (keyId: string) => {
    await api.revokeAccessKey(keyId);
    setKeys(keys.map((k) => (k.id === keyId ? { ...k, status: 'revoked' } : k)));
  };

  const handleRegisterBedrock = async () => {
    if (selectedKeyId && bedrockKey) {
      await api.registerBedrockKey(selectedKeyId, bedrockKey);
      setBedrockKey('');
      setSelectedKeyId(null);
      alert('Bedrock key registered');
    }
  };

  const handleDeactivate = async () => {
    if (!id) return;
    await api.deactivateUser(id);
    navigate('/users');
  };

  if (!user) return <div className="p-8">Loading...</div>;

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="bg-white rounded shadow p-6 mb-6">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-bold">{user.name}</h1>
            <p className="text-gray-500">{user.description || 'No description'}</p>
            <p className={`mt-2 ${user.status === 'active' ? 'text-green-500' : 'text-red-500'}`}>
              Status: {user.status}
            </p>
          </div>
          {user.status === 'active' && (
            <button onClick={handleDeactivate} className="bg-red-500 text-white px-4 py-2 rounded">
              Deactivate
            </button>
          )}
        </div>
      </div>

      <div className="bg-white rounded shadow p-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold">Access Keys</h2>
          {user.status === 'active' && (
            <button onClick={handleIssueKey} className="bg-blue-500 text-white px-4 py-2 rounded">
              Issue New Key
            </button>
          )}
        </div>

        {newKey && (
          <div className="bg-yellow-100 p-4 rounded mb-4">
            <p className="font-bold">New Key (copy now, shown only once):</p>
            <code className="block mt-2 p-2 bg-white rounded break-all">{newKey}</code>
            <button onClick={() => setNewKey(null)} className="mt-2 text-sm text-gray-500">
              Dismiss
            </button>
          </div>
        )}

        {selectedKeyId && (
          <div className="bg-blue-100 p-4 rounded mb-4">
            <p className="font-bold mb-2">Register Bedrock API Key</p>
            <input
              type="password"
              placeholder="Bedrock API Key"
              value={bedrockKey}
              onChange={(e) => setBedrockKey(e.target.value)}
              className="p-2 border rounded mr-2 w-64"
            />
            <button onClick={handleRegisterBedrock} className="bg-green-500 text-white px-4 py-2 rounded mr-2">
              Register
            </button>
            <button onClick={() => setSelectedKeyId(null)} className="text-gray-500">
              Cancel
            </button>
          </div>
        )}

        <table className="w-full">
          <thead>
            <tr className="border-b">
              <th className="text-left p-2">Prefix</th>
              <th className="text-left p-2">Status</th>
              <th className="text-left p-2">Region</th>
              <th className="text-left p-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {keys.map((key) => (
              <tr key={key.id} className="border-b">
                <td className="p-2 font-mono">{key.key_prefix}...</td>
                <td className="p-2">
                  <span className={key.status === 'active' ? 'text-green-500' : 'text-gray-500'}>
                    {key.status}
                  </span>
                </td>
                <td className="p-2">{key.bedrock_region}</td>
                <td className="p-2 space-x-2">
                  {key.status === 'active' && (
                    <>
                      <button
                        onClick={() => setSelectedKeyId(key.id)}
                        className="text-blue-500 text-sm"
                      >
                        Bedrock Key
                      </button>
                      <button onClick={() => handleRevoke(key.id)} className="text-red-500 text-sm">
                        Revoke
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
