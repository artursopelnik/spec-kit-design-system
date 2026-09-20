'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

interface Invoice {
  id: string;
  number: string;
  client: string;
  date: string;
  amount: number;
  status: 'paid' | 'pending' | 'overdue';
}

const SAMPLE_INVOICES: Invoice[] = [
  { id: '1', number: 'INV-001', client: 'Acme Corp', date: '2024-01-05', amount: 1500, status: 'paid' },
  { id: '2', number: 'INV-002', client: 'TechStart LLC', date: '2024-01-15', amount: 2200, status: 'paid' },
  { id: '3', number: 'INV-003', client: 'Global Inc', date: '2024-02-03', amount: 3000, status: 'pending' },
  { id: '4', number: 'INV-004', client: 'DataFlow Systems', date: '2024-02-20', amount: 1800, status: 'overdue' },
  { id: '5', number: 'INV-005', client: 'Acme Corp', date: '2024-03-10', amount: 2100, status: 'paid' },
];

export default function InvoicesPage() {
  const [invoices] = useState<Invoice[]>(SAMPLE_INVOICES);

  return (
    <main className="container mx-auto py-8">
      <h1 className="text-3xl font-bold mb-6">Invoices</h1>

      <div className="mb-6 space-y-2">
        <p className="text-sm text-muted-foreground">
          Filter invoices by billing period to track and analyze payments.
        </p>
      </div>

      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Invoice #</TableHead>
              <TableHead>Client</TableHead>
              <TableHead>Date</TableHead>
              <TableHead>Amount</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {invoices.map((invoice) => (
              <TableRow key={invoice.id}>
                <TableCell className="font-mono text-sm">{invoice.number}</TableCell>
                <TableCell>{invoice.client}</TableCell>
                <TableCell>{invoice.date}</TableCell>
                <TableCell className="text-right font-medium">${invoice.amount}</TableCell>
                <TableCell>
                  <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${
                    invoice.status === 'paid'
                      ? 'bg-green-100 text-green-800'
                      : invoice.status === 'pending'
                        ? 'bg-yellow-100 text-yellow-800'
                        : 'bg-red-100 text-red-800'
                  }`}>
                    {invoice.status}
                  </span>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </main>
  );
}
