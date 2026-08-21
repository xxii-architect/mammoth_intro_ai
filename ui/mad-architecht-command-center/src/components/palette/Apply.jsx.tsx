import React from 'react';
import styled from 'styled-components';

interface ApplyProps {
  title: string;
  description: string;
  onApply: () => void;
}

const Container = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(10px);
  border-radius: 15px;
  padding: 20px;
  box-shadow: 0 4px 30px rgba(0, 255, 255, 0.5);
  width: 300px;
  margin: 20px;
`;

const Title = styled.h2`
  color: #00ffff;
  font-size: 24px;
  margin-bottom: 10px;
`;

const Description = styled.p`
  color: #e0e0e0;
  font-size: 16px;
  text-align: center;
  margin-bottom: 20px;
`;

const ApplyButton = styled.button`
  background-color: #00ffff;
  color: #000;
  border: none;
  border-radius: 5px;
  padding: 10px 20px;
  cursor: pointer;
  font-size: 16px;
  transition: background-color 0.3s;

  &:hover {
    background-color: rgba(0, 255, 255, 0.8);
  }
`;

const Apply: React.FC<ApplyProps> = ({ title, description, onApply }) => {
  return (
    <Container>
      <Title>{title}</Title>
      <Description>{description}</Description>
      <ApplyButton onClick={onApply}>Apply Now</ApplyButton>
    </Container>
  );
};

export default Apply;