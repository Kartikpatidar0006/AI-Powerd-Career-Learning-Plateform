/**
 * Root application component.
 *
 * Wraps the entire app with the AuthProvider context and
 * renders the router.
 */

import { RouterProvider } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import router from './routes';

export default function App() {
  return (
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  );
}
