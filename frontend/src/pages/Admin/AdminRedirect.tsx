import { useNavigate } from 'react-router-dom';
import { useEffect } from 'react';

export default function AdminRedirect() {
    const navigate = useNavigate();
    
    useEffect(() => {
        navigate('/admin/management', { replace: true });
    }, [navigate]);
    
    return null;
}
